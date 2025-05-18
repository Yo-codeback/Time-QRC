import os, shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
from pyzbar.pyzbar import decode
import piexif
from datetime import datetime, timedelta

# ============= 共用工具 =============
def log(msg):
    log_text.insert(tk.END, msg + '\n')
    log_text.see(tk.END)

def parse_datetime_from_string(s):
    """支援西元／中文／民國格式 → datetime"""
    # 民國
    if "民國" in s:
        try:
            roc = int(s.split("民國")[1].split("年")[0])
            yyyy = roc + 1911
            rest = s.split("年")[1]
            mm = int(rest.split("月")[0])
            dd = int(rest.split("月")[1].split("日")[0])
            hms = rest.split("日")[1].replace("點", ":").replace("分", ":").replace("秒", "")
            hh, mi, ss = map(int, hms.split(":"))
            return datetime(yyyy, mm, dd, hh, mi, ss)
        except: return None
    # 其他
    for fmt in ("%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y年%m月%d日 %H點%M分%S秒"):
        try:
            return datetime.strptime(s, fmt)
        except: pass
    return None

def get_exif_datetime(path):
    try:
        dt = piexif.load(path)['Exif'][piexif.ExifIFD.DateTimeOriginal].decode()
        return datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        log(f"⚠️ EXIF 失敗：{e}")
        return None

def apply_time_shift_and_save(src_folder, offset_seconds):
    out_dir = os.path.join(src_folder, "output_fixed")
    os.makedirs(out_dir, exist_ok=True)
    for fn in os.listdir(src_folder):
        if not fn.lower().endswith(('.jpg', '.jpeg')): continue
        path = os.path.join(src_folder, fn)
        try:
            exif_dict = piexif.load(path)
            orig = datetime.strptime(
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal].decode(),
                "%Y:%m:%d %H:%M:%S"
            )
            new_dt = orig + timedelta(seconds=offset_seconds)
            dt_str = new_dt.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode()
            exif_dict['0th'][piexif.ImageIFD.DateTime] = dt_str.encode()
            Image.open(path).save(
                os.path.join(out_dir, fn),
                exif=piexif.dump(exif_dict)
            )
            log(f"🛠️ {fn} → {dt_str}")
        except Exception as e:
            log(f"💣 跳過 {fn}：{e}")

# ============= ⚡NEW! 雙 QR 掃描邏輯 =============
def scan_qr_images(folder):
    """掃描整個資料夾，找出含 QR 的照片清單"""
    qr_list = []
    for fn in os.listdir(folder):
        if not fn.lower().endswith(('.jpg','.jpeg','.png')): continue
        img_path = os.path.join(folder, fn)
        decoded = decode(Image.open(img_path))
        if decoded:
            txt = decoded[0].data.decode('utf-8')
            qr_dt = parse_datetime_from_string(txt)
            exif_dt = get_exif_datetime(img_path)
            if qr_dt and exif_dt:
                offset = (qr_dt - exif_dt).total_seconds()
                qr_list.append((fn, qr_dt, exif_dt, offset))
    return qr_list

# ============= UI 動作 =============
def start_process():
    folder = filedialog.askdirectory(title="選擇相機照片資料夾")
    if not folder: return
    log("🚀 開始處理：「"+folder+"」")

    qr_items = scan_qr_images(folder)
    if not qr_items:
        messagebox.showerror("找不到 QR", "😭 沒偵測到任何時間 QR！拍一張啦～")
        return

    # ⚡SUPER NEW! 多 QR 對時模式（平均所有 QR offset）
    total_offset = 0
    for fn, qr_dt, exif_dt, off in qr_items:
        log(f"🔍 {fn} → QR:{qr_dt} | EXIF:{exif_dt} | 差:{off} 秒")
        total_offset += off

    avg_offset = total_offset / len(qr_items)
    log(f"✨ 使用 {len(qr_items)} 張 QR 平均 offset = {avg_offset:.2f} 秒")

    for fn, qr_dt, exif_dt, off in qr_items:
        log(f"🔍 {fn} → QR:{qr_dt} | EXIF:{exif_dt} | 差:{off} 秒")
    if len(qr_items) == 1:
        avg_offset = qr_items[0][3]
        log("➔ 單 QR 模式：offset = "+str(avg_offset))
    else:
        avg_offset = sum(x[3] for x in qr_items)/len(qr_items)
        log(f"✨ 雙 QR 平均 offset = {avg_offset} 秒")

    apply_time_shift_and_save(folder, avg_offset)
    messagebox.showinfo("完成", "✅ 全部照片已校正完成！\n輸出於 output_fixed/")

# ============= Tkinter 介面 =============
root = tk.Tk()
root.title("📸 QR 對時神器 v1.1 – 雙 QR 版")
root.geometry("640x420")

tk.Button(root, text="選擇照片資料夾並校正", command=start_process,
          font=("Microsoft JhengHei",14), bg="#ffcc66").pack(pady=20)

log_text = tk.Text(root, width=80, height=16)
log_text.pack()

root.mainloop()
