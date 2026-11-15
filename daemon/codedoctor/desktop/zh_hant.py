"""繁體中文 (Traditional Chinese): the interface texts are written in Simplified Chinese, and for this language they are
converted where they reach the screen - by characters, with a few phrases first where one simplified character stands for
several traditional ones (复制 复杂 合并 ...). The web page gets the same table (boot_json) and converts the same way
(web/src/i18n.js), so both sides always agree.

The table covers every character the interface uses; a character not in it stays as it is, which is still readable.
"""

from __future__ import annotations

# Phrases first: one simplified character, several traditional ones.
PHRASES = (
    ("复制", "複製"), ("重复", "重複"), ("复杂", "複雜"), ("答复", "答覆"), ("回复", "回覆"), ("制作", "製作"), ("制造", "製造"),
    ("干净", "乾淨"), ("合并", "合併"), ("联系", "聯繫"), ("公里", "公里"), ("里程", "里程"), ("发现", "發現"), ("头发", "頭髮"),
    ("皇后", "皇后"), ("后台", "後台"), ("采样", "取樣"), ("软件", "軟體"), ("内存", "記憶體"), ("默认", "預設"), ("文件夹", "資料夾"),
    ("文件", "檔案"), ("服务器", "伺服器"), ("网络", "網路"), ("信息", "資訊"), ("视频", "影片"), ("音频", "音訊"), ("鼠标", "滑鼠"),
    ("键盘", "鍵盤"), ("程序", "程式"), ("代码", "程式碼"), ("数据库", "資料庫"), ("数据", "資料"), ("设置", "設定"), ("登录", "登入"),
    ("用户", "使用者"), ("支持", "支援"), ("屏幕", "螢幕"), ("硬盘", "硬碟"), ("进程", "行程"), ("线程", "執行緒"), ("接口", "介面"),
    ("项目", "專案"), ("质量", "品質"), ("缓存", "快取"), ("打印", "列印"), ("链接", "連結"), ("搜索", "搜尋"), ("下载", "下載"),
    ("上传", "上傳"), ("调用", "呼叫"), ("命令", "指令"), ("终端", "終端機"), ("窗口", "視窗"), ("菜单", "選單"), ("图标", "圖示"),
)

# simplified -> traditional, character by character (written as pairs: 简繁简繁...)
PAIRS = (
    "万萬与與专專业業东東丝絲丢丟两兩个個为為举舉么麼义義乐樂书書买買争爭于於云雲产產亿億仅僅从從仓倉价價优優伪偽侦偵侧側们們儿兒"
    "关關兵兵册冊写寫冲衝决決况況冻凍准準减減凭憑几幾击擊创創删刪别別刚剛剧劇办辦动動务務励勵区區医醫协協单單历歷压壓参參双雙发發变變"
    "号號叶葉吗嗎听聽启啟员員响響唤喚啰囉喽嘍团團围圍国國图圖圆圓场場坏壞块塊报報声聲处處备備复復头頭夹夾够夠奖獎学學实實审審宽寬对對"
    "寻尋导導将將尽盡层層属屬岁歲币幣帧幀带帶帮幫应應库庫开開异異弃棄张張强強归歸当當录錄径徑忆憶总總态態愿願戏戲战戰户戶执執扩擴择擇"
    "担擔拟擬拦攔拥擁挂掛挥揮损損换換据據挡擋挤擠数數断斷无無旧舊时時显顯晓曉暂暫术術机機杂雜权權条條来來极極构構标標栏欄树樹样樣检檢楼樓"
    "欢歡残殘毕畢汇匯汉漢没沒测測济濟浏瀏溃潰满滿滚滾点點灯燈炼煉状狀独獨献獻环環现現画畫监監盖蓋盘盤码碼础礎硅矽确確离離种種称稱稳穩"
    "穷窮竞競笔筆简簡类類粘黏紧緊约約级級纯純纸紙线線练練组組细細织織终終绍紹经經结結给給络絡绝絕统統继繼绩績绪緒续續维維绸綢综綜绿綠"
    "缓緩编編缩縮网網习習联聯脑腦脚腳腾騰获獲荐薦蓝藍补補装裝规規视視览覽见見触觸计計订訂认認让讓训訓议議讯訊记記许許论論设設访訪证證"
    "评評诉訴诊診词詞译譯试試话話询詢该該详詳语語误誤说說请請读讀谁誰调調谢謝谱譜贴貼费費资資赖賴赛賽账帳购購败敗跃躍踪蹤车車轨軌转轉"
    "轮輪轻輕载載较較辑輯输輸边邊达達迁遷过過运運还還这這进進远遠违違连連适適选選逻邏遗遺释釋里裡钟鐘钥鑰钮鈕银銀链鏈销銷锁鎖错錯键鍵"
    "镜鏡长長门門闭閉问問闲閒间間阅閱队隊阶階际際陆陸险險随隨难難页頁顶頂项項顺順须須顿頓预預频頻题題颜顏额額风風马馬驳駁验驗骤驟麦麥"
    "并並后後占佔范範采採档檔签簽浅淺潜潛划劃幂冪咨諮觉覺众眾兑兌党黨储儲却卻厂廠县縣卫衛叙敘吓嚇妈媽孙孫宠寵尝嘗尔爾岛島师師"
    "帅帥广廣彻徹恶惡悬懸惊驚惯慣扑撲扫掃扰擾掷擲摄攝摆擺撑撐杀殺杨楊汤湯涂塗渐漸湾灣烦煩烧燒热熱爱愛猫貓获獲阳陽阴陰东東则則"
    "会會电電红紅节節观觀桥橋恒恆仪儀债債偿償兴興养養华華卖賣厅廳吨噸园園坛壇夺奪奋奮妇婦宪憲尘塵岗崗弥彌恋戀恳懇悦悅惩懲愤憤拣揀挣掙捞撈搁擱摇搖敌敵斗鬥旷曠柜櫃栈棧梦夢椭橢欧歐沟溝沪滬泽澤洁潔浓濃涛濤湿濕灭滅灾災炉爐爷爺牵牽犹猶狱獄琐瑣疗療盏盞矿礦税稅窃竊笼籠筑築纠糾纤纖纺紡纽紐绑綁绒絨绘繪缆纜罗羅罚罰职職肤膚胜勝脏髒艺藝苹蘋虑慮虽雖蚂螞衬襯袜襪讲講讶訝诚誠诞誕谈談谊誼贝貝负負贡貢财財责責贤賢质質贺賀赔賠赠贈趋趨轩軒软軟递遞邮郵邻鄰酿釀针針钉釘钢鋼钱錢铃鈴铁鐵铜銅铺鋪阁閣阔闊陈陳隐隱韩韓顾顧领領馆館驱驅鱼魚鸟鳥鸡雞黄黃齐齊龙龍龟龜"
)


def _table() -> dict[int, str]:
    table: dict[int, str] = {}
    for i in range(0, len(PAIRS) - 1, 2):
        table[ord(PAIRS[i])] = PAIRS[i + 1]
    return table


_TABLE = _table()
_CACHE: dict[str, str] = {}


def convert(text: str) -> str:
    """Simplified -> traditional: phrases, then characters."""
    if not text:
        return text
    hit = _CACHE.get(text)
    if hit is not None:
        return hit
    out = text
    for a, b in PHRASES:
        if a in out:
            out = out.replace(a, b)
    out = out.translate(_TABLE)
    if len(_CACHE) > 20000:
        _CACHE.clear()
    _CACHE[text] = out
    return out


def catalog() -> dict:
    """What the page needs to do the same (web/src/i18n.js)."""
    return {"hant": {"pairs": PAIRS, "phrases": [list(p) for p in PHRASES]}}
