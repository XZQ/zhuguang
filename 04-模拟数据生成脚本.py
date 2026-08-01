# 模拟数据生成脚本
# 用途:生成连锁便利店多店模拟数据,用于方案演示 / 复赛 Demo / Skill 效果验证。
# 运行:python3 04-模拟数据生成脚本.py -> 输出到 data/ 目录(CSV,utf-8)

import csv
import random
import os
from datetime import datetime, timedelta

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ============ 配置 ============
NUM_STORES = 12
NUM_SKUS = 40
SIM_DAYS = 14  # 模拟近 14 天
TEMP_INTERVAL_MIN = 30  # 冷柜每 30 分钟一条

# 门店:3 个商圈 × 2 店型
BZ = ["CBD", "社区", "校园"]
STORES = []
for i in range(NUM_STORES):
    STORES.append({
        "store_id": f"S{i+1:02d}",
        "name": f"便利S{i+1:02d}号店",
        "bz": BZ[i % 3],
        "type": "旗舰" if i % 3 == 0 else "标准",
        "area": random.randint(60, 150),
    })

# SKU:品类
CATS = ["饮料", "乳品", "零食", "日化", "鲜食"]
SKUS = []
for i in range(NUM_SKUS):
    SKUS.append({
        "sku_id": f"K{i+1:04d}",
        "name": f"SKU{i+1}",
        "cat": CATS[i % 5],
        "price": round(random.uniform(3, 35), 2),
    })

# 异常注入清单(为了让演示有戏):(store_id, 异常类型, 开始日)
INJECT = {
    "coldchain": [("S03", 10), ("S07", 12)],   # S03 店 10 天前开始冷柜超温, S07 店 12 天前
    "stockout": [("S05", 13)],                  # S05 店某 SKU 缺货
    "price_tag": [("S08", 13)],                 # S08 店价签错误
}

def store_rows():
    rows = []
    for s in STORES:
        rows.append([s["store_id"], s["name"], s["bz"], s["type"], s["area"]])
    return rows

def sales_rows():
    rows = []
    start = datetime.now() - timedelta(days=SIM_DAYS)
    for d in range(SIM_DAYS):
        day = start + timedelta(days=d)
        for s in STORES:
            base = 100 if s["bz"] == "CBD" else (80 if s["bz"] == "社区" else 60)
            for h in range(7, 24):
                # 高峰:7-9 点 / 12-13 点 / 18-20 点
                peak = 1.0 + (0.8 if h in (7, 8, 12, 13) else (1.2 if 18 <= h <= 20 else 0))
                n_sales = random.randint(2, max(3, int(base * peak * 0.05)))
                for _ in range(n_sales):
                    sku = random.choice(SKUS)
                    ts = day + timedelta(hours=h, minutes=random.randint(0, 59))
                    # 冷柜异常店:低温商品(乳品/鲜食)销量下降
                    if s["store_id"] in [i for i, _ in INJECT["coldchain"]] and (day - start).days >= dict(INJECT["coldchain"]).get(s["store_id"], 99) and sku["cat"] in ("乳品", "鲜食"):
                        if random.random() < 0.6:
                            continue
                    rows.append([ts.strftime("%Y-%m-%d %H:%M"), s["store_id"], sku["sku_id"], sku["cat"], random.randint(1, 3), round(sku["price"] * random.randint(1, 2), 2)])
    return rows

def inventory_rows():
    rows = []
    for s in STORES:
        for sku in SKUS:
            days_to_expire = random.randint(2, 25) if sku["cat"] in ("乳品", "鲜食") else random.randint(30, 120)
            stock = random.randint(5, 50)
            # S05 店 K0015 缺货注入
            if s["store_id"] == "S05" and sku["sku_id"] == "K0015":
                stock = 0
                days_to_expire = 1
            safety = random.randint(10, 20)
            rows.append([s["store_id"], sku["sku_id"], sku["cat"], stock, safety, days_to_expire])
    return rows

def iot_rows():
    rows = []
    start = datetime.now() - timedelta(days=SIM_DAYS)
    interval = timedelta(minutes=TEMP_INTERVAL_MIN)
    t = start
    end = start + timedelta(days=SIM_DAYS)
    cold_affected = {sid: day for sid, day in INJECT["coldchain"]}
    while t < end:
        for s in STORES:
            day_index = (t - start).days
            temp = 3.5 + random.uniform(-0.3, 0.3)
            if s["store_id"] in cold_affected and day_index >= cold_affected[s["store_id"]]:
                temp = 7.5 + random.uniform(0.2, 1.2)  # 超温(标准应 ≤5℃)
            rows.append([t.strftime("%Y-%m-%d %H:%M"), s["store_id"], f"FROST-{s['store_id']}", round(temp, 1)])
        t += interval
    return rows

def price_rows():
    rows = []
    for s in STORES:
        for sku in SKUS:
            sys_price = sku["price"]
            tag_price = sys_price
            pos_price = sys_price
            if s["store_id"] == "S08" and sku["sku_id"] == "K0020":
                tag_price = round(sys_price * 0.8, 2)  # 价签标错
            rows.append([s["store_id"], sku["sku_id"], sys_price, tag_price, pos_price])
    return rows

def write_csv(fname, header, rows):
    path = os.path.join(OUT_DIR, fname)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"✔ {fname}: {len(rows)} 行")

def main():
    write_csv("stores.csv", ["store_id", "name", "bz", "type", "area"], store_rows())
    write_csv("pos_sales.csv", ["ts", "store_id", "sku_id", "cat", "qty", "amount"], sales_rows())
    write_csv("inventory.csv", ["store_id", "sku_id", "cat", "stock", "safety_stock", "days_to_expire"], inventory_rows())
    write_csv("iot_coldchain.csv", ["ts", "store_id", "device_id", "temp_c"], iot_rows())
    write_csv("price.csv", ["store_id", "sku_id", "system_price", "tag_price", "pos_price"], price_rows())
    print(f"\n输出目录: {OUT_DIR}")

if __name__ == "__main__":
    main()
