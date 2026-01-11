import asyncio
import random
import tkinter as tk
from tkinter import messagebox
from bleak import BleakScanner, BleakClient

# --- 設定 ---
TARGET_ADDRESS = "E2:4D:31:4C:FE:26"
WRITE_UUID = "40ee2222-63ec-4b7f-8ce7-712efd55b90e"

class BluetoothApp:
    def __init__(self, loop):
        self.loop = loop
        self.client = None
        self._is_destroyed = False 
        
        self.root = tk.Tk()
        self.root.title("BLE 周期制御コントローラー")
        self.root.geometry("400x550")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.is_connected = tk.BooleanVar(value=False)
        self.is_running = tk.BooleanVar(value=False)
        self.current_speed = tk.IntVar(value=0)
        self.fluctuation_speed = tk.IntVar(value=0)
        
        self.direction = tk.IntVar(value=1)
        self.base_period = tk.IntVar(value=10)
        self.fluctuation_period = tk.IntVar(value=0)
        
        self.step_count = 0
        self.target_steps = 10

        self.setup_ui()

    def setup_ui(self):
        self.conn_btn = tk.Button(self.root, text="デバイスに接続", command=self.toggle_connection, bg="lightgray")
        self.conn_btn.pack(pady=10, ipadx=20)
        self.status_label = tk.Label(self.root, text="未接続", fg="red")
        self.status_label.pack()

        tk.Frame(self.root, height=2, bd=1, relief=tk.SUNKEN).pack(fill="x", padx=20, pady=10)

        tk.Label(self.root, text="ベーススピード (0 - 100)").pack()
        self.speed_scale = tk.Scale(self.root, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.current_speed, length=300)
        self.speed_scale.pack()

        tk.Label(self.root, text="速度のゆらぎ幅 (±n)").pack()
        tk.Spinbox(self.root, from_=0, to=50, textvariable=self.fluctuation_speed, width=10).pack()

        tk.Frame(self.root, height=2, bd=1, relief=tk.SUNKEN).pack(fill="x", padx=20, pady=10)

        tk.Label(self.root, text="反転周期 (ステップ数: 1回=0.1秒)").pack()
        tk.Spinbox(self.root, from_=1, to=200, textvariable=self.base_period, width=10).pack()
        
        tk.Label(self.root, text="周期のゆらぎ (±nステップ)").pack()
        tk.Spinbox(self.root, from_=0, to=100, textvariable=self.fluctuation_period, width=10).pack()

        self.mode_btn = tk.Button(self.root, text="自動実行 開始", command=self.toggle_mode, bg="lightblue", state=tk.DISABLED)
        self.mode_btn.pack(pady=20, ipadx=20)

        self.log_text = tk.Label(self.root, text="接続してください", font=("MS Gothic", 10), fg="blue")
        self.log_text.pack(pady=10)

    def update_status(self, text, color="black"):
        """安全にステータスラベルを更新する"""
        if not self._is_destroyed:
            self.status_label.config(text=text, fg=color)

    def on_close(self):
        self._is_destroyed = True
        self.is_running.set(False)
        self.root.destroy()

    def toggle_connection(self):
        if not self.is_connected.get():
            self.conn_btn.config(state=tk.DISABLED) # 二重押し防止
            asyncio.run_coroutine_threadsafe(self.connect_ble(), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.disconnect_ble(), self.loop)

    async def connect_ble(self):
        try:
            # 1. デバイス検索の明示
            self.update_status(f"デバイス探索中... ({TARGET_ADDRESS})", "orange")
            device = await BleakScanner.find_device_by_address(TARGET_ADDRESS, timeout=5.0)
            
            if not device:
                self.update_status("デバイスが見つかりませんでした", "red")
                self.conn_btn.config(state=tk.NORMAL)
                return

            # 2. 接続試行
            self.update_status("接続を確立中...", "blue")
            self.client = BleakClient(device)
            await self.client.connect()
            
            if not self._is_destroyed:
                self.is_connected.set(True)
                self.update_status("接続成功！", "green")
                self.conn_btn.config(text="切断", bg="salmon", state=tk.NORMAL)
                self.mode_btn.config(state=tk.NORMAL)
                self.log_text.config(text="準備完了")
        except Exception as e:
            if not self._is_destroyed:
                self.update_status("接続エラー", "red")
                self.conn_btn.config(state=tk.NORMAL)
                messagebox.showerror("Error", f"接続失敗: {e}")

    async def disconnect_ble(self):
        if self.client:
            self.update_status("切断中...", "orange")
            try:
                await self.client.write_gatt_char(WRITE_UUID, bytes([0x01, 0x01, 0x00]), response=True)
                await self.client.disconnect()
            except: pass
        if not self._is_destroyed:
            self.is_connected.set(False)
            self.is_running.set(False)
            self.update_status("未接続", "red")
            self.conn_btn.config(text="デバイスに接続", bg="lightgray")
            self.mode_btn.config(text="自動実行 開始", bg="lightblue", state=tk.DISABLED)

    def toggle_mode(self):
        if self.is_running.get():
            self.is_running.set(False)
            self.mode_btn.config(text="自動実行 開始", bg="lightblue")
            self.send_ble_command(0, self.direction.get())
        else:
            self.update_target_steps()
            self.is_running.set(True)
            self.mode_btn.config(text="自動実行 停止", bg="orange")

    def update_target_steps(self):
        base = self.base_period.get()
        fluc = self.fluctuation_period.get()
        self.target_steps = max(1, base + random.randint(-fluc, fluc))
        self.step_count = 0

    def send_ble_command(self, speed, direction):
        if not self.is_connected.get() or self._is_destroyed: return
        
        val = speed if direction == 1 else (128 + speed)
        if speed == 0: val = 0
        
        asyncio.run_coroutine_threadsafe(
            self.client.write_gatt_char(WRITE_UUID, bytes([0x01, 0x01, val]), response=True),
            self.loop
        )
        
        if not self._is_destroyed:
            d_str = "正転" if direction == 1 else "逆転"
            self.log_text.config(text=f"【{d_str}】 速度:{speed} (反転まで:{self.target_steps - self.step_count})")

    async def control_logic_loop(self):
        while not self._is_destroyed:
            if self.is_running.get() and self.is_connected.get():
                base_s = self.current_speed.get()
                fluc_s = self.fluctuation_speed.get()
                
                send_speed = max(0, min(100, base_s + random.randint(-fluc_s, fluc_s))) if fluc_s > 0 else base_s

                self.step_count += 1
                if self.step_count >= self.target_steps:
                    self.direction.set(0 if self.direction.get() == 1 else 1)
                    self.update_target_steps()

                self.send_ble_command(send_speed, self.direction.get())

            await asyncio.sleep(0.1)

    async def run_tk(self):
        try:
            while not self._is_destroyed:
                self.root.update()
                await asyncio.sleep(0.05)
        except (tk.TclError, RuntimeError):
            pass

async def main():
    loop = asyncio.get_running_loop()
    app = BluetoothApp(loop)
    await asyncio.gather(app.run_tk(), app.control_logic_loop())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass