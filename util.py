# -*- coding: utf-8 -*-
import atexit
from dotenv import load_dotenv, find_dotenv
import re
from dashscope import Generation
import streamlit as st
from PIL import Image
import edge_tts
import requests
import jieba
import random
from pypinyin import pinyin, Style
from contextlib import contextmanager
from pathlib import Path

from config import *

# 加载环境变量
_ = load_dotenv(find_dotenv())
api_key = os.getenv("DASHSCOPE_API_KEY")

def init_sample_images():
    """初始化示例图片目录"""
    os.makedirs("images", exist_ok=True)  # 修改路径，确保与代码中的使用一致
    for level, categories in QUESTION_TYPES.items():
        for category, types in categories.items():
            for type_name in types:
                img_path = f"images/{level}_{category}_{type_name}.jpg"
                if not os.path.exists(img_path):
                    Image.new('RGB', (300, 200), color=(70, 130, 180)).save(img_path)

def get_completion(prompt, model="qwen-plus"):
    """调用大模型API"""
    try:
        response = Generation.call(
            model=model,
            prompt=prompt,
            api_key=api_key,
        )
        return response.output.text
    except Exception as e:
        st.error(f"API调用失败: {str(e)}")
        return None

def clean_json_response(raw_response):
    """清理API返回的JSON数据"""
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return None

def get_hsk_level(level_str):
    """从HSK级别字符串中提取数字"""
    match = re.search(r'\d+', level_str)
    return int(match.group()) if match else 1

def select_word_level_by_hsk(hsk_level):
    """根据HSK等级随机选择词库级别"""
    if hsk_level < 1 or hsk_level > 6:
        hsk_level = 1  # 默认使用HSK1

    rand = random.random()
    cumulative_weight = 0

    for level in range(1, 7):
        cumulative_weight += HSK_WEIGHT_CONFIG[hsk_level][level - 1]
        if rand < cumulative_weight:
            return level

    return 6  # 默认返回最高等级

def adjust_text_by_hsk(text, hsk_level):
    """根据HSK等级调整文本中的词汇"""
    # 处理非字符串输入
    if not isinstance(text, str):
        try:
            text = str(text)  # 尝试转换为字符串
        except:
            st.warning(f"无法处理类型为 {type(text).__name__} 的选项，已跳过调整")
            return text

    words = jieba.cut(text) if 'jieba' in globals() else list(text)
    adjusted_words = []
    for word in words:
        target_level = select_word_level_by_hsk(hsk_level)
        target_words = get_words_by_level(target_level)
        if word in target_words or len(word) <= 1:
            adjusted_words.append(word)
        else:
            if target_words:
                adjusted_words.append(random.choice(list(target_words)))
            else:
                adjusted_words.append(word)
    return ''.join(adjusted_words)

def get_words_by_level(level):
    """获取指定HSK级别的词汇集合"""
    level_key = f"HSK_{level}"
    return HSK_WORDS.get(level_key, set())

def is_chinese_text(text):
    """判断文本是否主要为中文"""
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    return chinese_chars / len(text) > 0.2 if text else False


# ========== 听力题文字转语音 ==========
async def text_to_speech(text, save_path="output.mp3", level="HSK4", voice='female', role='male'):
    """将文字内容转换为语音并保存为MP3，支持男女声切换"""
    hsk_num = get_hsk_level(level)
    adjusted_text = adjust_text_by_hsk(text, hsk_num)
    rate = HSK_SPEECH_RATE.get(level, "-15%")

    # 根据语言和性别选择合适的语音
    lang = 'zh' if is_chinese_text(adjusted_text) else 'en'
    voice_id = VOICE_MAPPING[voice][lang]

    communicate = edge_tts.Communicate(
        text=adjusted_text,
        voice=voice_id,
        rate=rate
    )
    await communicate.save(save_path)
    return save_path


def play_audio_in_streamlit(audio_path):
    """在Streamlit中播放音频"""
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    st.audio(audio_bytes, format="audio/mp3")


# 添加音频合并函数
def combine_audio_files(audio_files, output_file):
    """合并多个音频文件为一个"""
    from pydub import AudioSegment

    combined = AudioSegment.empty()
    for file in audio_files:
        audio = AudioSegment.from_mp3(file)
        combined += audio

    combined.export(output_file, format="mp3")


@contextmanager
def temporary_audio_files():
    """创建临时音频文件并在使用完毕后清理"""
    temp_files = []
    try:
        yield temp_files
    finally:
        for file_path in temp_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    st.warning(f"无法删除临时文件 {file_path}: {str(e)}")

def generate_image_from_text(description):
    """使用百度千帆API生成图像"""
    access_token = "bce-v3/ALTAK-rAPN53AiNtSX1IXUEjVOK/7e8fd6c1dd61d0afe80c292f98ab84e1fc904561"

    url = "https://qianfan.baidubce.com/v2/images/generations"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }

    payload = {
        "model": "irag-1.0",
        "prompt": description,
        "size": "512x512"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_json = response.json()

        if "data" in response_json and "url" in response_json["data"][0]:
            image_url = response_json["data"][0]["url"]
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            return image_response.content
        else:
            st.warning(f"图片生成失败：{response_json}")
            return None
    except Exception as e:
        st.warning(f"图片生成出错：{e}")
        return None

def add_pinyin(text):
    pinyin_list = pinyin(text, style=Style.TONE)
    pinyin_text = ' '.join([p[0] for p in pinyin_list])
    return f"{text}({pinyin_text})"


def generate_prompt(level, category, question_types, num_questions=5):
    """生成动态Prompt，根据详细配置细化每个题型的要求"""
    hsk_num = get_hsk_level(level)
    # 基础词库限制
    vocab_restriction = f"""
       【词汇限制】
       1. 严格按照HSK{hsk_num}词库权重配置使用词汇：
       - HSK1: 80% HSK1词汇, 20% HSK2-3词汇
       - HSK2: 20% HSK1以下, 65% HSK2, 15% HSK3-4
       - HSK3: 20% HSK2以下, 60% HSK3, 20% HSK4-5
       - HSK4: 20% HSK3以下, 60% HSK4, 20% HSK5-6
       - HSK5: 20% HSK4以下, 70% HSK5, 10% HSK6
       - HSK6: 30% HSK5以下, 70% HSK6
       2. 禁止使用超出该级别的词汇或复杂语法
       3. 选项设置以及题目只能是词库里的词汇
       """
    grammar_requirement = ""
    if level == "HSK1":
        grammar_requirement = hsk1_grammar
    elif level == "HSK2":
        grammar_requirement = hsk2_grammar
    elif level == "HSK3":
        grammar_requirement = hsk3_grammar
    elif level == "HSK4":
        grammar_requirement = hsk4_grammar
    elif level == "HSK5":
        grammar_requirement = hsk5_grammar
    elif level == "HSK6":
        grammar_requirement = hsk6_grammar

    # 构建每个题型的详细要求
    type_specific_requirements = []
    for type_name in question_types:
        if level in DETAILED_QUESTION_CONFIG and category in DETAILED_QUESTION_CONFIG[level] and type_name in \
                DETAILED_QUESTION_CONFIG[level][category]:
            config = DETAILED_QUESTION_CONFIG[level][category][type_name]
            reqs = []

            if config.get("require_audio", False):
                reqs.append(f"- 必须包含语音内容，语音内容要求：{config['audio_content']}")

            if config.get("require_image", False):
                reqs.append("- 必须包含图片描述，图片内容应与题目内容相关")

            if config.get("question_content"):
                reqs.append(f"- 题目内容要求：{config['question_content']}")

            # 处理特殊问题格式
            if config.get("question_format"):
                if config.get("generate_contrast", False):
                    reqs.append(f"- 题目内容必须包含与图片内容不同的物品或描述，用于判断对错")
                reqs.append(f"- 题目必须包含一个问题，格式为：{config['question_format']}")

            reqs.append(f"- 题目内容至少包含 {config['min_words']} 个汉字")
            reqs.append(f"- 选项数量最多为 {config['max_options']} 个")
            reqs.append(f"- 词汇级别要求：{config['vocab_level']}")

            type_specific_requirements.append(f"""
【{type_name} 题型要求】
{chr(10).join(reqs)}
""")

    # 整合所有要求
    specific_reqs_text = "\n".join(type_specific_requirements) if type_specific_requirements else ""

    # 生成示例（只保留与当前选中题型相关的示例）
    relevant_examples = []
    for example in get_examples():
        if example["type"] in question_types:
            relevant_examples.append(example)

    return f"""
你是一个专业的HSK{level}出题系统，请生成以下题型题目：
{', '.join(question_types)}
{vocab_restriction}

【语法要求】
{grammar_requirement}

【详细题型要求】
{specific_reqs_text}

【题目规则】
1. 共生成{num_questions}道题。
2. 保持题型多样性。
3. 难度符合HSK{level}大纲。
4. 每次启动程序生成的题目都要不一样，要十分严格的执行这一条规则。
5. 选项要有干扰项，干扰强度随着HSK等级逐级提升。
6. 生成的图片尽量写实，最好是真人的。
7. 图片排序图是五段毫不相关的dialogues。
8. 所有的题目都只能是单选题。
9. 生成的图片与文字描述要一致。
10.必要的时候可以调用工具。

【输出格式】
{{
  "questions": [
    {{
      "type": "题型名称",
      "content": "题目内容",
      "passages": ["所需的文章或段落"],
      "questions": ["问题1", "问题2", ...],  // 新增字段
      "target_sentence":"目标句子",
      "gaps":["第一空","第二空, ..."]
      "dialogues":["第一句","第二句",...]
      "options": ["A", "B", ...],  // 选择题需要
      "answer": "正确答案",
      "explanation": "答案解析",  // 可选
      "audio_content": ["语音内容（如果有）","第二句",...],
      "audio_question": "语音问题（如果有）",
      "image_description": ["图片1描述（如果有）","图片2描述"，...],
      "sentences": ["句子1", "句子2", ...]  // 新增字段，用于存储填空题的句子
    }}
  ]

}}
【题型示例】
{json.dumps(relevant_examples, ensure_ascii=False, indent=2)}
"""


# 自动清理临时文件的上下文管理器
@contextmanager
def manage_temp_files():
    temp_files = []
    try:
        yield temp_files
    finally:
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                st.warning(f"无法清理文件: {file_path} ({str(e)})")

def cleanup_temp_files():
    """清理所有临时文件"""
    if 'temp_files' in st.session_state:
        for file_path in st.session_state.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                st.warning(f"无法清理文件: {file_path} ({str(e)})")

        # 重置列表
        st.session_state.temp_files = []


# 注册应用退出时自动清理
atexit.register(cleanup_temp_files)

def get_examples():
    """返回所有题型的示例"""
    return [
        {
            "type": "听录音选择题",
            "content": "我女儿今年6岁，她喜欢吃中国菜",
            "audio_content": "我女儿今年6岁，她喜欢吃中国菜",
            "question_content": "他女儿几岁了?",
            "options": [
                "6岁",
                "8岁",
                "9岁",
            ],
            "answer": "A",
            "explanation": "录音中提到他女儿今年6岁",
        },
        {
            "type": "听力看图判断题",
            "content": "足球",
            "question": "一个小男孩在踢足球，对还是错？",
            "options": [
                "对",
                "错"
            ],
            "answer": "对",
            "audio_content": "踢足球",
            "image_description": "踢足球"
        },
        {
            "type": "阅读看图判断题",
            "content": "先生",
            "question": "根据图片和词语，判断对错",
            "options": [
                "对",
                "错"
            ],
            "answer": "错",
            "image_description": "一位女士"
        },
        {
            "type": "选词填空题",
            "sentences": [
                "那个人是我的（）。",
                "我看见了，小狗在椅子（）。",
                "喂，妈，我（）爸爸坐明天下午5点的飞机回去。",
                "小朋友你（）岁了。",
                "（）你请我喝茶。"
            ],
            "options": [
                "A.和",
                "B.后面",
                "C.几",
                "D.学生",
                "E.谢谢"],
            "answers": ["D", "B", "A", "C", "E"]  # 对应每个句子的正确选项
        },
        {
            "type": "看图选择题",
            "content": "请根据听到的内容选择对应的图片。",
            "question": "音频中描述的是哪张图片？",
            "options": ["猫", "狗", "鸟"],
            "option_images": ["猫", "狗", "鸟"],
            "answer": "B",
            "explanation": "音频中提到了狗，所以正确答案是B。",
            "audio_content": "狗。"
        },
        {
            "type": "文字判断题",
            "audio_content": "昨天晚上雨下得很大，城市的街道像是被洗过一样，变得非常干净。",
            "target_sentence": "昨天晚上下了大雪",
            "answer": "错"
        },
        {
            "type": "问答匹配题",
            "questions": [
                {"index": "1", "text": "上午谁去火车站？"},
                {"index": "2", "text": "你什么时候来？"},
                {"index": "3", "text": "我的汉语书呢？"},
                {"index": "4", "text": "你们那儿下雨了吗？"},
                {"index": "5", "text": "这个杯子多少钱？"},
            ],
            "options": [
                {"text": "20分钟后"},
                {"text": "在这儿"},
                {"text": "没"},
                {"text": "我"},
                {"text": "17块"},

            ],
            "answers": ["D", "A", "B", "C", "E"]  # 正确答案
        },
        {
            "type": "阅读判断题",
            "content": "今天下午我要给学生上新课,但是我还没有准备好。",
            "question": "他是老师",
            "answer": "对",
            "explanation": "文中提到要给学生上课，所以可以判断他是老师。"
        },
        {
            "type": "句子匹配题",
            "sentences": [
                "这个篮球是送给我的吗?",
                "是的,张先生已经告诉我了.",
                "对不起，茶和咖啡都没有了.",
                "好，我也想多运动运动呢.",
                "你也在这儿工作吗？",
            ],
            "options": [
                "你知道那件事了?",
                "明天早上我们一起去跑步吧。",
                "没关系，我喝水吧。",
                "对，希望你喜欢。",
                "是的，我就在前面那家公司上班。",
            ],
            "answers": ["D", "A", "C", "B", "E"],  # 正确答案
            "explanations": [
                "D选项直接回应了篮球是否是送的问题",
                "A选项与第二句中的'已经告诉我了'相呼应",

            ]
        },
        {
            "type": "阅读理解题",
            "passages": ["为了眼睛的健康，我们不要长时间玩儿手机或者电脑，看书时也不要让眼睛离得太近。"],
            "question": "根据这段话，我们应该注意什么？",
            "options": ["多吃鱼", "早点儿起床", "少玩儿手机"],
            "answer": "C"
        },
        {
            "type": "阅读理解题1v2",
            "passages": [
                "很多人都羡慕导游，觉得他们能到处儿玩。其实，做导游并不像人们想的那样轻松。首先，导游要对景点非常地了解，而且讲解时还要想办法引起游客的兴趣。其次，导游每天都要走很多路，只有能吃苦，才能坚持下来。另外，旅行中会出现各种各样的问题，导游必须能够冷静地解决问题。"],
            "questions": [
                {
                    "text": "很多人羡慕导游，是因为导游？",
                    "options": [
                        "A. 工资高",
                        "B. 假期长",
                        "C. 知识丰富",
                        "D. 能去各地玩儿"
                    ],
                    "answer": "D",
                    "explanation": "开头提到..."
                },
                {
                    "text": "根据这段话，可以知道什么？？",
                    "options": [
                        "A. 门票很贵",
                        "B. 游客没耐心",
                        "C. 信心很关键",
                        "D. 导游工作辛苦"
                    ],
                    "answer": "D",
                    "explanation": "根据文章内容，导游工作很辛苦..."
                }
            ]
        },

        {
            "type": "听对话选择题",
            "question": "听对话，根据问题选答案",
            "audio_content": "上午女儿来电话了。她说什么了？她说她七月八号回家，你生日的前一天。太好了，我很想她。女儿哪天回家?",
            "audio_question": "女儿哪天回家？",
            "options": ["2月3日", "7月8日", "12月6日"],
            "answer": ""
        },
        {
            "type": "图片匹配题",
            "sentences": [
                "这些报纸我已经看完了。",
                "您的东西到了，请您在这儿写一下名字。",
                "这个电脑现在卖多少钱？",
                "你知道第三题是什么意思吗？",
                "西瓜很好吃，你多吃几块。"
            ],
            "options": [
                "A. 一个女人抱着一堆报纸",
                "B. 切好的西瓜",
                "C. 女孩向男孩请教问题",
                "D. 男人举着一台笔记本电脑",
                "E. 快递员送货上门"
            ],
            "answer": ["A", "E", "D", "C", "B"],
            "image_description":[
                "女人抱着报纸",
                "切好的西瓜",
                "女孩向男孩请教问题",
                "男人举着一台笔记本电脑",
                "快递员送货上门"
            ]
        },
        {
            "type": "图片匹配题2",
            "sentences": [
                "再见,医生,回家后我会多出去走走的。",
                "这边的椅子都没人坐,我们就坐这里吧。",
                "水果太少了,我再去洗一些",
                "这些鱼多少钱?",
                "前面人多,你开车的时候慢点儿."
            ],
            "options": [
                "A. 鱼",
                "B. 司机握住方向盘",
                "C. 一排空椅子",
                "D. 洗水果",
                "E. 病人和医生道别"
            ],
            "answer": ["E", "C", "D", "A", "B"],
            "image_description": [
                "鱼",
                "司机握住方向盘",
                "一排空椅子",
                "洗水果",
                "病人和医生道别"
            ]
        },
        {
            "type": "图片排序题",
            "dialogues": [
                "钱小姐你的电话，好的谢谢。",
                "你看，这个衣服怎么样? 很漂亮。",
                "你买什么东西了？都是你爱吃的东西。",
                "我们去哪吃饭?前面有个饭馆，我们去那儿。",
                "这个字谁会读。老师，我会！"
            ],
            "options": [
                "一个男生伸手指前面",
                "一个女学生在回答问题",
                "一个男生举着电话",
                "一购物车的东西",
                "一对情侣在服装店买衣服"
            ],
            "answer": ["C", "E", "D", "A", "B"],
            "explanations": [
                "对话中提到接电话，所以对应选项C",
                "对话讨论衣服，所以对应选项E",
                "对话提到购物，所以对应选项D",
                "对话讨论去饭馆吃饭，所以对应选项A",
                "对话是课堂场景，所以对应选项B"
            ]
        },
        {
            "type": "连词成句",
            "words": ["事情", "被他", "了", "解决", "已经"],
            "answer": "事情已经被他解决了",
            "explanation": "这是一个被动句式，'被'字表明动作的承受者是'事情'，'已经'表示动作完成，按照中文语法规则，正确语序为'事情已经被他解决了'。"
        },
        {
            "type": "听对话选择题1v2",
            "audio_content": "听力材料文本...",
            "questions": [
                {
                    "id": 1,
                    "text": "人们为什么要考试？",
                    "options": ["A. 反应问题", "B. 获得机会", "C. 不想去工作", "D. 养成好习惯"],
                    "answer": "B",
                    "explanation": "根据听力材料中...",
                    "audio_enabled": True,  # 可为每个问题单独配置
                    "audio_path": None  # 可选：预先生成的音频路径
                },
                {
                    "id": 2,
                    "text": "要看到世界的精彩需要什么？",
                    "options": ["A. 友谊", "B. 高级眼镜", "C. 知识和经验", "D. 流利的中文"],
                    "answer": "C",
                    "explanation": "材料明确指出...",
                    "audio_enabled": True
                }
            ]

        },
        {
            "type": "听对话选择题1v3",
            "audio_content": "听力材料文本...",
            "questions": [
                {
                    "id": 1,
                    "text": "小和尚为什么很头疼？",
                    "options": ["A. 胃口不好", "B. 和师傅吵架了", "C. 打扫落叶很费事", "D. 师傅催他快点儿干完"],
                    "answer": "C",
                    "explanation": "根据听力材料中...",
                    "audio_enabled": True,  # 可为每个问题单独配置
                    "audio_path": None  # 可选：预先生成的音频路径
                },
                {
                    "id": 2,
                    "text": "小和尚听到办法后是怎么做的？",
                    "options": ["A. 把树砍了", "B. 使劲儿摇树", "C. 找师傅商量", "D. 找人轮流打扫"],
                    "answer": "B",
                    "explanation": "材料明确指出...",
                    "audio_enabled": True
                },
                {
                    "id": 3,
                    "text": "这段话主要想告诉我们什么？",
                    "options": ["A. 要乐观", "B. 要活在当下", "C. 对人要坦率", "D. 做事要灵活"],
                    "answer": "B",
                    "explanation": "材料明确指出...",
                    "audio_enabled": True
                }
            ]
        },
        {
            "type": "听对话选择题1v5",
            "audio_content": "听力材料文本...",
            "questions": [
                {
                    "id": 1,
                    "text": "欢乐谷的设计理念是什么？",
                    "options": ["A. 娱乐休闲", "B. 参与体验", "C. 观赏享受", "D. 资源整合"],
                    "answer": "B",
                    "explanation": "根据听力材料中...",
                    "audio_enabled": True,  # 可为每个问题单独配置
                    "audio_path": None  # 可选：预先生成的音频路径
                },
                {
                    "id": 2,
                    "text": "欢乐谷建在北京的重要原因是什么？",
                    "options": ["A. 北京游客众多", "B. 北京是中国的首都", "C. 北京缺少时尚主题公园", "D. 北京有很多文化旅游景点"],
                    "answer": "C",
                    "explanation": "材料明确指出...",
                    "audio_enabled": True
                },
                {
                    "id": 3,
                    "text": "欢乐谷与嘉年华在哪方面有相似之处？",
                    "options": ["A. 景观", "B. 表演", "C. 主题活动", "D. 娱乐设备"],
                    "answer": "D",
                    "explanation": "材料明确指出...",
                    "audio_enabled": True
                },
                {
                    "id": 4,
                    "text": "欢乐谷的演艺队伍有多少人？",
                    "options": ["A. 20多", "B. 100多", "C. 200多", "D. 300多"],
                    "answer": "C",
                    "explanation": "材料明确指出...",
                    "audio_enabled": True
                },
                {
                    "id": 5,
                    "text": "为游客提供时间表和导游图的目的是什么？",
                    "options": ["A. 宣传大型活动", "B. 游客能自由规划游玩路线", "C. 提醒游客地址和营业时间", "D. 游客能玩遍欢乐谷所有项目"],
                    "answer": "B",
                    "explanation": "材料明确指出...",
                    "audio_enabled": True
                },
            ]
        },
        {
            "type": "句子排序题",
            "sentences": [
                "A.你是否也有这样的特点呢",  # 注意：句子需包含标签（A/B/C）
                "B.比如说，做事努力、对自己要求严格等",
                "C.调查发现，优秀的人都有一些共同点。"
            ],
            "answer": ["C", "B", "A"],  # 正确顺序（标签列表）
            "explanation": "首句总述共同点（C），接着举例（B），最后提问（A），符合逻辑顺序。"
        },
        {
            "type": "短文选词填空题5",
            "passages": "一位英明的国王公开选拔法官，有三个人毛 遂自荐:一个是贵族，一个是曾经( 1 )国王南征北战的武士，还有一个是普通的教师。国王领着他们来到池塘边，池塘上漂浮着几个橙子。国王问贵族:“池塘里一共漂着几个橙子?”贵族走到近前数了数，回答:“一共是6个，陛下。”(2)，又问了武士同样的问题。武士甚至没有走近，就 ( 3 )， 说:“我也看到6个，陛下!”国王仍旧没有说话，又转向教师。教师并没有急于回答，他脱掉鞋子，径直走进池塘里，把橙子拿了出来。“陛下，一共是三个橙子。因为它们都被从中间切开了。”国王非常高 兴，( 4)道:“只有你才是合适的人选。只有你知道不能轻易地下结论，因为我们看到的并不都是事情的真相。",
            "gaps": [
                {
                    "gap_number": 1,
                    "options": [
                        "A. 陪伴",
                        "B. 协调",
                        "C. 组织",
                        "D. 执行"
                    ],
                    "answer": "A",
                    "explanation": ""
                },
                {
                    "gap_number": 2,
                    "options": [
                        "A. 贵族很得意",
                        "B. 国王没有表态",
                        "C. 国王连连点头",
                        "D. 大家哈哈大笑"
                    ],
                    "answer": "B",
                    "explanation": ""
                },
                {
                    "gap_number": 3,
                    "options": [
                        "A. 直接",
                        "B. 正式",
                        "C. 紧急",
                        "D. 明显"
                    ],
                    "answer": "A",
                    "explanation": ""
                },
                {
                    "gap_number": 4,
                    "options": [
                        "A. 命令",
                        "B. 答应",
                        "C. 欣赏",
                        "D. 称赞"
                    ],
                    "answer": "D",
                    "explanation": ""
                }
            ]
        },
        {
            "type": "短文选词填空题6",
            "passages": [
                "现在人们工作生活节奏都很快，办事都1.______效率，对养生也常常2.______，希望一个养生法子几天就能见效。才过十天半月，就想把几年甚至几十年积累的问题3.______；又缺乏耐心，好了伤疤忘了痛，身体4.______有了起色就又开始纵容自己，把养生的成果在5.______期就给毁掉了，实在是非常可惜。"
            ],
            "gaps": [  # 每个空位的信息（顺序对应短文中的数字编号）
                {
                    "gap_number": 1,
                    "options": [
                        "A. 遵循",
                        "B. 讲求",
                        "C. 讲究",
                        "D. 请求"
                    ],
                    "answer": "B",
                    "explanation": "搭配‘效率’，‘讲求’表示追求、重视，符合语境"
                },
                {
                    "gap_number": 2,
                    "options": [
                        "A. 循序渐进",
                        "B. 急于求成",
                        "C. 再接再厉",
                        "D. 刻不容缓"
                    ],
                    "answer": "B",
                    "explanation": "与后文‘几天就能见效’对应，体现急于求成的心态"
                },
                {
                    "gap_number": 3,
                    "options": [
                        "A. 川流不息",
                        "B. 一扫而空",
                        "C. 统筹兼顾",
                        "D. 一举两得"
                    ],
                    "answer": "B",
                    "explanation": "指希望快速消除积累的问题，‘一扫而空’表示彻底清除"
                },
                {
                    "gap_number": 4,
                    "options": [
                        "A. 万一",
                        "B. 一旦",
                        "C. 不妨",
                        "D. 一度"
                    ],
                    "answer": "B",
                    "explanation": "‘一旦’表示假设的条件，符合‘有了起色就纵容自己’的逻辑"
                },
                {
                    "gap_number": 5,
                    "options": [
                        "A. 起初",
                        "B. 萌芽",
                        "C. 最初",
                        "D. 发育"],
                    "answer": "B",
                    "explanation": "‘萌芽期’指事物刚开始发展的阶段，与‘成果被毁掉’呼应"
                }
            ],
        },
        {
            "type": "阅读文章选择题",
            "passages": "一个富翁丢了钱包，十分着急，他广贴告示说，如果有人能替他把钱包找回来，他就把钱包里的金币分一半儿给那个人。几天后，有一个人找到了钱包，将它还给富翁。吝啬的富翁见到找回的钱包非常高兴，却又舍不得拿出一半儿金币。他眼珠一转，故作惊慌地说：“钱包里少了一枚钻石戒指。”那个人坚称自己从未见过钻石戒指。两人争吵起来，决定让法官来裁决。法官早就听闻富翁为人吝啬，便问富翁：“你敢肯定钱包里除了100枚金币，还有一枚钻石戒指吗？”“是的，我可以发誓！我的戒指就在钱包里！”富翁说。“那好，”法官接着说，“这个钱包里只有100枚金币，没什么钻石戒指。由此可以断定，这个钱包并不是你丢的那个。你还是去找里边有钻石戒指的钱包吧。",
            "questions": [
                {
                    "text": "第2段中，画线词语“吝啬“最可能是什么意思？",
                    "options": ["A. 小气", "B. 谨慎", "C. 谦虚", "D. 自私"],
                    "answer": "A",
                    "explanation": "根据上下文，富翁不愿分金币，可知“吝啬”意为小气"
                },
                {
                    "text": "富翁看见找回的钱包后？",
                    "options": ["A. 感到很吃惊", "B. 发现自己被骗了", "C. 给了那个人五十枚金币", "D. 谎称里面原来有枚戒指"],
                    "answer": "D",
                    "explanation": "文中提到富翁故意说钱包少了戒指"
                },
                {
                    "text": "法官怎么样?",
                    "options": ["A. 不相信富翁", "B. 把钱包还给了富翁", "C. 认为那个人是小偷", "D. 要求那个人赔偿戒指"],
                    "answer": "A",
                    "explanation": "法官通过反问和裁决表明不相信富翁的说法"
                },
                {
                    "text": "最适合做上文标题的是？",
                    "options": ["A. 富翁的烦恼", "B. 钱包里的戒指", "C. 金币去哪了", "D. 占小便宜的法官"],
                    "answer": "B",
                    "explanation": "“戒指”是故事的关键线索，贯穿全文"
                }
            ]
        },
        {
            "type": "长文本理解题",
            "text": "铁树开花具有很强的地域性。在热带，铁树生长10年后就能开花结果。但当它被移植到中国寒冷干燥的地方时，就很少开花了。即使是室内盆栽的铁树，有的往往也要几十年甚至上百年才能开花，所以人们就用“铁树开花”来比喻极难实现或非常罕见的事情。",
            "questions": [
                {
                    "text": "选出与文本内容一致的一项",
                    "options": [
                        "A. 铁树寿命短",
                        "B. 盆栽铁树年年开花",
                        "C. 铁树开花需要一定的气候条件",
                        "D. 铁树开花在热带地区很罕见"
                    ],
                    "answer": "C",
                    "explanation": "根据文章内容，铁树开花在热带较为常见，而在寒冷干燥的地方很少开花，说明需要一定的气候条件，因此选项C正确。"
                }
            ]
        },
        {
            "type": "短文选句填空题",
            "passages": [
                "1911年4月，利比里亚商人哈桑在挪威买了12000吨鲜鱼，运回利比里亚首府后，一过秤，鱼竟一下子少了47吨。哈桑回想购鱼时他是亲眼看着过秤的，一点儿也没少啊，__1__，无人动过鱼。那么这47吨鱼上哪儿去了呢？哈桑百思不得其解。后来，这桩奇案终于大白于天下，__2__。地球重力是指地球引力与地球离心力的合力。地球的重力值会随地球纬度的增加而增加，赤道处最小，两极最大。同一个物体若在两极重190公斤，拿到赤道，就会减少1公斤。挪威所处纬度高，靠近北极；利比里亚的纬度低，靠近赤道，__3__。哈桑的鱼丢失了分量，就是因为不同地区的重力差异造成的。__4__，也为1980年墨西哥奥运会连破多项世界纪录这一奇迹找到了答案。墨西哥城在北纬不到20度、海拔2240米处，__5__，正因为地心引力相对较小，运动健儿们奇迹般地一举打破了多项世界纪录。"
            ],
            "gaps": [  # 每个空位的信息（顺序对应短文中的__1__至__5__）
                {
                    "gap_number": 1,
                    "options": ["A. 归途中平平安安", "B. 比一般城市远离地心1500米", "C. 原来是地球的重力“偷”走了鱼", "D. 地球的重力值也随之减少",
                                "E. 地球重力的地区差异"],
                    "answer": "A",
                    "explanation": "与后文‘无人动过鱼’衔接，说明运输过程平安，排除人为因素"
                },
                {
                    "gap_number": 2,
                    "options": ["A. 归途中平平安安", "B. 比一般城市远离地心1500米", "C. 原来是地球的重力“偷”走了鱼", "D. 地球的重力值也随之减少",
                                "E. 地球重力的地区差异"],
                    "answer": "C",
                    "explanation": "揭示奇案的原因，与后文地球重力的解释直接关联"
                },
                {
                    "gap_number": 3,
                    "options": ["A. 归途中平平安安", "B. 比一般城市远离地心1500米", "C. 原来是地球的重力“偷”走了鱼", "D. 地球的重力值也随之减少",
                                "E. 地球重力的地区差异"],
                    "answer": "D",
                    "explanation": "承接前文纬度差异，说明重力值随纬度降低而减少"
                },
                {
                    "gap_number": 4,
                    "options": ["A. 归途中平平安安", "B. 比一般城市远离地心1500米", "C. 原来是地球的重力“偷”走了鱼", "D. 地球的重力值也随之减少",
                                "E. 地球重力的地区差异"],
                    "answer": "E",
                    "explanation": "总结前文重力差异的影响，引出后文奥运会案例"
                },
                {
                    "gap_number": 5,
                    "options": ["A. 归途中平平安安", "B. 比一般城市远离地心1500米", "C. 原来是地球的重力“偷”走了鱼", "D. 地球的重力值也随之减少",
                                "E. 地球重力的地区差异"],
                    "answer": "B",
                    "explanation": "解释墨西哥城的特殊地理位置，与地心引力较小直接相关"
                }
            ]
        },
        {
            "type": "病句选择题",
            "question": "选出有语病的一项",
            "options": [
                "A. 人人都需要关爱，关爱能增近两个人的感情，拉近两个人的距离。但是，这种关爱的前提是适度。",
                "B. 人们在财务困境中挣扎的一个原因是：他们在学校里学习多年，却没有学到任何关于金钱方面的知识。",
                "C. 1940年11月27日出生的李小龙，虽然不是最早进入好莱坞的华人，却是最早成为国际巨星的功夫演员。",
                "D. 作为一名翻译工作者，一方面要努力学好外语，一方面要学好本民族语言也是非常重要的，两者缺一不可。"
            ],
            "answer": "D",
            "explanation": "D句句式杂糅，“一方面要……”与“……也是非常重要的”重复，应删去“也是非常重要的”。",
            "error_type": "句式杂糅"
        },
        {
            "type": "文章选择题",
            "passages": [  # 文章内容（支持多段落列表）
                "白领福利好、收入高、职位稳定，是令人羡慕的职业。但是令人羡慕的白领也有自己的苦恼，每月刚发完薪水，还完房贷及信用卡，添置些衣物，和同事朋友潇洒一回，一番冲动之后发现这个月的工资又“白领”了。为什么让人艳羡的白领精英会沦落到如此地步呢?这是因为这些白领的财务处于“亚健康”状态，他们之前没有及时地发现自己家庭存在的财务隐患，日积月累容易造成危机的爆发。",
                "统计发现，白领阶层常见的财务隐患有:消费不健康、流动性不健康、家庭保障不健康、收入构成过于单一、获取投资收益的能力不足等。",
                "那么，白领精英如何才能发现家庭财务隐患呢?目前网上的“理财体检服务”针对不同的客户需求推出三种理财体检套餐，分别为标准理财体检套餐、精英理财体检套餐、贵宾理财体检套餐。其中，标准套餐包括6项理财指标诊断，可以解决一般家庭的财务诊断需求;精英套餐包括10项理财指标诊断,可进一步细致地诊断家庭的财务健康状况;贵宾套餐包括14项理财指标诊断，将对客户的家庭财务进行全面的诊断。专家建议一般3至6个月需要对自己的家庭财务进行一次诊断。另外，当家庭财务出现重大变化时，比如买房、买车等大额支出或奖金收入、项目分成等大额收入，这时也需要对家庭财务重新进行一次理财体检。"
            ],
            "questions": [  # 问题列表（每个问题包含文本、选项、答案、解析关键词）
                {
                    "question_id": 1,
                    "text": "根据上文，白领有什么苦恼？",
                    "options": [
                        "A. 工作非常辛苦",
                        "B. 福利不怎么样",
                        "C. 体检机制不完善",
                        "D. 许多人有财务危机"
                    ],
                    "answer": "D",
                    "explanation_key": "工资又“白领”了，财务处于“亚健康”状态，存在财务隐患"  # 解析时引用的原文关键句
                },
                {
                    "question_id": 2,
                    "text": "理财体检服务”有什么特点？",
                    "options": [
                        "A. 需要提前预约",
                        "B. 可以免费体检半年",
                        "C. 专为公司财务设计",
                        "D. 包含多种体检套餐"
                    ],
                    "answer": "D",
                    "explanation_key": "推出三种理财体检套餐：标准、精英、贵宾"
                },
                {
                    "question_id": 3,
                    "text": "针对家庭理财，专家的建议是？",
                    "options": [
                        "A. 要买保险",
                        "B. 要制定消费计划",
                        "C. 定期进行财务诊断",
                        "D. 在大额支出前咨询专家"
                    ],
                    "answer": "C",
                    "explanation_key": "建议一般3至6个月进行一次财务诊断"
                },
                {
                    "question_id": 4,
                    "text": "关于白领，下列哪项正确？",
                    "options": [
                        "A. 投资能力不足",
                        "B. 喜欢网上购物",
                        "C. 收入来源较多",
                        "D. 许多人处于亚健康状态"
                    ],
                    "answer": "A",
                    "explanation_key": "常见财务隐患包括获取投资收益的能力不足"
                }
            ]
        },
        {
            "type": "听短文选择题",
            "content": "请听下面的文章，然后回答问题。",
            "audio_content": "体育课上，一个学生被老师点名去示范跳高...（完整文章）",
            "questions": [
                {
                    "question": "那个同学为什么会被大家嘲笑？",
                    "options": ["A. 上课走神了", "B. 跳法很奇怪", "C. 动作很笨拙", "D. 没越过横杆"],
                    "answer": "B",
                    "explanation": "文章提到学生背对着横杆跳过去，同学们哄然大笑，说明是跳法奇怪导致被嘲笑。"
                },
                {
                    "question": "关于那个同学，下列哪项正确？",
                    "options": ["A. 擅长射击", "B. 被老师批评了", "C. 打破了奥运会记录", "D. 现为著名的田径教练"],
                    "answer": "C",
                    "explanation": "文章明确提到他跃过了二点二四米，打破了奥运会记录。"
                },
                {
                    "question": "这段话主要想告诉我们什么？",
                    "options": ["A. 要敢于说不", "B. 要坚持自己的选择", "C. 错误是不可避免的", "D. 要善于从错误中寻找契机"],
                    "answer": "D",
                    "explanation": "文章最后总结了主旨：从错误中发现成功的契机。"
                }
            ]
        }
        # 其他示例...
    ]


def show_question_type_example(level, category, type_name):
    img_dir = Path("images")
    img_path = img_dir / f"{level}_{category}_{type_name}.jpg"

    with st.expander(f"{TYPE_ICONS.get(type_name, '')} {type_name}", expanded=False):
        try:
            if img_path.exists():
                st.image(str(img_path))  # 关键：将Path对象转为字符串
            else:
                st.warning(f"图片不存在: {img_path}")
        except Exception as e:
            st.error(f"加载示例失败: {str(e)}")