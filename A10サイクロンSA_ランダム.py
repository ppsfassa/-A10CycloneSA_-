import asyncio
import random
from bleak import BleakClient

# --- 設定 ---
TARGET_ADDRESS = "E2:4D:31:4C:FE:26"
WRITE_UUID = "40ee2222-63ec-4b7f-8ce7-712efd55b90e"

# 状態管理用の変数
is_running = False

async def control_loop(client):
    """デバイス制御のメインループ（別タスクで実行）"""
    global is_running
    current_speed = 0
    current_direction = 1

    print("\n[操作説明]")
    print("Enterキーを押すと [ランダム開始] / [一時停止] が切り替わります")
    print("Ctrl+C でプログラムを完全に終了します\n")

    try:
        while True:
            if is_running:
                # --- ランダムロジック ---
                change_chance = random.random()
                if change_chance < 0.1 or current_speed == 0:
                    state_dice = random.random()
                    if state_dice < 0.1: current_speed = random.randint(0, 100)
                    elif state_dice < 0.2: current_speed = 0
                    elif state_dice < 0.5: current_speed = random.randint(40, 60)
                    elif state_dice < 0.8: current_speed = random.randint(60, 85)
                    else: current_speed = random.randint(85, 100)
                else:
                    if current_speed > 0:
                        current_speed += random.randint(-3, 3)
                        current_speed = max(10, min(current_speed, 100))
                
                if current_speed == 0:
                    current_direction = 0
                elif change_chance < 0.9:
                    current_direction = 1 if current_direction == 0 else 0

                val = current_speed if current_direction == 1 else (0x80 + current_speed)
                if current_speed == 0: val = 0x00

                await client.write_gatt_char(WRITE_UUID, bytes([0x01, 0x01, val]), response=True)
                print(f"\r運行中: {'正転' if current_direction else '逆転'} Speed:{current_speed:3}   ", end="", flush=True)
            
            else:
                # 停止状態（何もしない）
                await asyncio.sleep(0.1)
                continue

            await asyncio.sleep(0.5)

    except asyncio.CancelledError:
        pass

async def main():
    global is_running
    print(f"{TARGET_ADDRESS} に接続中...")
    
    async with BleakClient(TARGET_ADDRESS) as client:
        if not client.is_connected:
            print("接続失敗")
            return
        
        print("接続成功！")

        # 制御ループをタスクとして開始
        task = asyncio.create_task(control_loop(client))

        try:
            while True:
                # ユーザーの入力を非同期で待機
                await asyncio.to_thread(input, "") 
                
                # 状態を反転
                is_running = not is_running
                
                if is_running:
                    print("\n>>> ランダム回転 開始！")
                else:
                    # 停止時は即座に速度0を送る
                    print("\n>>> 一時停止（速度0を送信中...）")
                    await client.write_gatt_char(WRITE_UUID, bytes([0x01, 0x01, 0x00]), response=True)
                    print(">>> 待機中... (再開するにはEnter)")

        except KeyboardInterrupt:
            print("\nプログラムを終了します。")
            task.cancel()
            if client.is_connected:
                await client.write_gatt_char(WRITE_UUID, bytes([0x01, 0x01, 0x00]), response=True)
                print("最終停止信号を送信しました。")

if __name__ == "__main__":
    asyncio.run(main())