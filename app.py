import requests
import re
from flask import Flask, render_template, request, jsonify

# --- Flask应用初始化 ---
app = Flask(__name__)

# --- 核心配置与逻辑 (与我们之前的桌面应用几乎完全相同) ---
HEADERS = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://static.sporttery.cn/',
    'Origin': 'https://static.sporttery.cn',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
FIXED_PRIZES = { "三等奖": 10000.0, "四等奖": 3000.0, "五等奖": 300.0, "六等奖": 200.0, "七等奖": 100.0, "八等奖": 15.0, "九等奖": 5.0 }

def fetch_lottery_data():
    """获取最新的30期开奖数据"""
    try:
        url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
        params = {'gameNo': 85, 'pageSize': 30, 'provinceId': 0, 'isVerify': 1, 'pageNo': 1}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            # 解析数据
            parsed = []
            for item in data.get('value', {}).get('list', []):
                raw_prizes = {p.get('prizeLevel'): p for p in item.get('prizeLevelList', [])}
                parsed.append({
                    'draw_number': item.get('lotteryDrawNum'),
                    'draw_date': item.get('lotteryDrawTime'),
                    'front_area': item.get('lotteryDrawResult', '').split()[:5],
                    'back_area': item.get('lotteryDrawResult', '').split()[5:],
                    'prizes': raw_prizes
                })
            return sorted(parsed, key=lambda x: x['draw_number']) # 返回按期号升序的数据
        else:
            return None
    except Exception:
        return None

def calculate_prize(front_hits, back_hits, api_prizes, is_additional):
    """计算单注中奖金额"""
    level_map = {(5, 2):"一等奖",(5, 1):"二等奖",(5, 0):"三等奖",(4, 2):"四等奖",(4, 1):"五等奖",(3, 2):"六等奖",(4, 0):"七等奖",(3, 1):"八等奖",(2, 2):"八等奖",(3, 0):"九等奖",(1, 2):"九等奖",(2, 1):"九等奖",(0, 2):"九等奖"}
    level = level_map.get((front_hits, back_hits))
    if not level: return None, 0, 0
    base_p = FIXED_PRIZES[level] if level in FIXED_PRIZES else float(api_prizes.get(level, {}).get('stakeAmount', '0').replace(',', '').replace('---', '0'))
    add_p = 0.0
    if is_additional and level not in ["七等奖", "九等奖"]:
        add_str = api_prizes.get(f"{level}(追加)", {}).get('stakeAmount', '0').replace(',', '').replace('---', '0')
        if add_str: add_p = float(add_str)
    return level, base_p, add_p

# --- Web接口 ---
@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_winnings():
    """处理中奖查询请求"""
    data = request.json
    user_numbers_raw = data.get('numbers', '').strip().split('\n')
    start_draw = data.get('start_draw', '')
    num_draws = int(data.get('num_draws', 5))
    is_additional = data.get('is_additional', False)
    
    lottery_data = fetch_lottery_data()
    if not lottery_data:
        return jsonify({"error": "无法获取开奖数据，请稍后再试。"}), 500
        
    # 清理和验证用户号码
    user_numbers = []
    for line in user_numbers_raw:
        line = re.sub(r'\|', '', line).strip() # 移除可能的分隔符
        if re.match(r"^\s*(\d{1,2}\s+){6}\d{1,2}\s*$", line):
            user_numbers.append(line)

    if not user_numbers:
        return jsonify({"error": "请输入有效的号码。"}), 400

    # 查找起始期数
    start_index = next((i for i, d in enumerate(lottery_data) if d['draw_number'] == start_draw), -1)
    if start_index == -1:
        return jsonify({"error": f"未在最近30期数据中找到起始期号: {start_draw}"}), 404

    results_html = ""
    total_winnings = 0.0
    end_index = min(start_index + num_draws, len(lottery_data))

    for i in range(start_index, end_index):
        draw = lottery_data[i]
        results_html += f"<h4>--- 核对 第 {draw['draw_number']} 期 ({draw['draw_date']}) ---</h4>"
        
        for user_set in user_numbers:
            parts = user_set.split()
            user_front, user_back = set(f"{int(n):02d}" for n in parts[:5]), set(f"{int(n):02d}" for n in parts[5:])
            
            front_m = len(set(draw['front_area']).intersection(user_front))
            back_m = len(set(draw['back_area']).intersection(user_back))

            level, base_p, add_p = calculate_prize(front_m, back_m, draw['prizes'], is_additional)
            
            text = f"<p>号码 [{user_set}]: "
            if level:
                total_winnings += base_p + add_p
                text += f"<span class='win'><b>中奖！【{level}】，奖金 {base_p:,.2f} 元</b></span>"
                if add_p > 0: text += f"<span class='add-win'><b> + 追加 {add_p:,.2f} 元。</b></span>"
                else: text += "。"
            else:
                text += "未中奖。"
            results_html += f"{text}</p>"
    
    return jsonify({
        "results_html": results_html,
        "total_winnings": f"{total_winnings:,.2f}"
    })

if __name__ == '__main__':
    # 在本地运行时，可以让局域网内的手机访问
    # 找到你电脑的IP地址（如192.168.1.100），手机访问 http://192.168.1.100:5000
    app.run(host='0.0.0.0', port=5000)
