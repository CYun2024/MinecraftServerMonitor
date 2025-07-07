import os
from datetime import datetime, timedelta
import random

# 日志文件路径（与主程序中的LOG_FILE一致）
LOG_FILE = "server_status.log"

# 预设的服务器地址列表
SERVER_ADDRESSES = [
    "127.0.0.1:25565",
    "mc.example.com:25565",
    "192.168.1.100",
    "play.myserver.net:25566",
    "survival.server.com",
    "creative.mcserver.org:25567",
    "factions.pvp.net",
    "skyblock.mine.com:25568",
    "modded.server.io"
]

# 预设的MOTD列表
MOTD_LIST = [
    "Welcome to Minecraft Server!",
    "Survival Multiplayer - Have fun!",
    "Creative Builders Paradise",
    "Adventure Awaits - Explore Now!",
    "Pixelmon Reforged Server",
    "SkyBlock Challenge - Start from scratch",
    "Ultimate Factions PvP",
    "BedWars Tournament - Join Now!",
    "Modded Madness - 200+ Mods",
    "Vanilla Survival - Pure Experience",
    "Hardcore Mode - One Life Only!",
    "Economy Server - Earn & Trade"
]

def generate_test_log(days=30):
    """生成指定天数的测试日志"""
    # 删除现有日志文件（如果存在）
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    
    current_date = datetime.now()
    start_date = current_date - timedelta(days=days)
    
    # 生成日志
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        date = start_date
        while date <= current_date:
            # 为每天随机选择一个服务器地址
            server_address = random.choice(SERVER_ADDRESSES)
            
            # 跳过部分天数（模拟服务器离线日）
            if random.random() < 0.2:  # 20%的概率跳过这一天
                date += timedelta(days=1)
                continue
            
            # 每天随机1-3个会话
            session_count = random.randint(1, 3)
            last_end_time = None
            
            for i in range(session_count):
                # 确定开始时间
                if last_end_time:
                    # 与前一个会话间隔1-6小时
                    gap_hours = random.randint(1, 6)
                    start_time = last_end_time + timedelta(hours=gap_hours)
                else:
                    # 当天的随机时间（8:00-20:00之间）
                    start_hour = random.randint(8, 20)
                    start_minute = random.randint(0, 59)
                    start_time = datetime(date.year, date.month, date.day, start_hour, start_minute)
                
                # 确定持续时间（1-12小时）
                duration_hours = random.randint(1, 12)
                end_time = start_time + timedelta(hours=duration_hours)
                
                # 如果会话跨天，调整结束时间到当天23:59
                if end_time.date() > start_time.date():
                    end_time = datetime(start_time.year, start_time.month, start_time.day, 23, 59)
                
                # 随机选择一个MOTD
                motd = random.choice(MOTD_LIST)
                
                # 随机决定是否标记为估计时间
                start_estimated = random.random() < 0.1  # 10%的概率
                end_estimated = random.random() < 0.1   # 10%的概率
                
                # 格式化日志行 - 适配新格式
                start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                
                if start_estimated:
                    start_str += "*"
                if end_estimated:
                    end_str += "*"
                
                # 新格式: [服务器地址] [上线] 开始时间 ~ 结束时间 | MOTD: ...
                log_line = f"[{server_address}] [上线] {start_str} ~ {end_str} | MOTD: {motd}\n"
                f.write(log_line)
                
                last_end_time = end_time
            
            # 随机生成一些在线时间很短的会话（模拟服务器重启）
            if random.random() < 0.3:  # 30%的概率
                restart_count = random.randint(1, 3)
                for _ in range(restart_count):
                    # 在最后结束时间后立即重启
                    start_time = last_end_time + timedelta(minutes=random.randint(1, 10))
                    end_time = start_time + timedelta(minutes=random.randint(1, 30))
                    new_motd = random.choice(MOTD_LIST)
                    
                    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 新格式
                    log_line = f"[{server_address}] [上线] {start_str} ~ {end_str} | MOTD: {new_motd}\n"
                    f.write(log_line)
                    last_end_time = end_time
            
            # 移动到下一天
            date += timedelta(days=1)
    
    # 添加当前仍在运行的会话（每个服务器一个）
    for server_address in SERVER_ADDRESSES:
        if random.random() < 0.5:  # 50%的概率为该服务器添加一个仍在运行的会话
            last_session_start = current_date - timedelta(hours=random.randint(1, 6))
            motd = random.choice(MOTD_LIST)
            start_str = last_session_start.strftime("%Y-%m-%d %H:%M:%S") + "*"
            
            # 新格式
            log_line = f"[{server_address}] [上线] {start_str} ~ 无 | MOTD: {motd}\n"
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
    
    print(f"已生成 {days} 天的测试日志到: {LOG_FILE}")
    print(f"包含 {len(SERVER_ADDRESSES)} 个服务器地址的日志数据")

if __name__ == "__main__":
    # 生成30天的测试日志
    generate_test_log(30)
