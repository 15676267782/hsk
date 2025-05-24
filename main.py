import json
import os
import re
from dotenv import load_dotenv, find_dotenv
from dashscope import Generation
import streamlit as st
from PIL import Image
import edge_tts
import asyncio
import uuid
import requests
import jieba
import random
from pypinyin import pinyin, Style
import time
from contextlib import contextmanager

# 加载环境变量
_ = load_dotenv(find_dotenv())
api_key = os.getenv("DASHSCOPE_API_KEY")

# 题型配置字典（包含图标和示例图片）
QUESTION_TYPES = {
    "HSK1": {
        "听力": ["听力看图判断题", "看图选择题", "图片排序题", "听录音选择题"],
        "阅读": ["阅读看图判断题", "图片匹配题", "问答匹配题", "选词填空题"]
    },
    "HSK2": {
        "听力": ["听力看图判断题", "图片排序题", "听对话选择题"],
        "阅读": ["图片匹配题", "选词填空题", "阅读判断题", "句子匹配题"]
    },
    "HSK3": {
        "听力": ["图片排序题", "文字判断题", "听对话选择题"],
        "阅读": ["选词填空题", "句子匹配题", "阅读理解题"],
        "写作": ["连词成句", "根据拼音写汉字"]
    },
    "HSK4": {
        "听力": ["文字判断题", "听对话选择题4", "听对话选择题1v2"],
        "阅读": ["选词填空题", "阅读理解题", "句子排序题", "阅读理解题1v2"]
    },
    "HSK5": {
        "听力": ["听对话选择题5", "听对话选择题1v3"],
        "阅读": ["短文选词填空题5", "长文本理解题", "阅读文章选择题"],
        "对话": ["情景对话题"]  # 特别添加对话题型
    },
    "HSK6": {
        "听力": ["听短文选择题", "听对话选择题6", "听对话选择题1v5"],
        "阅读": ["短文选词填空题6", "病句选择题", "短文选句填空题", "文章选择题"]
    }
}

# 题型图标和示例图片映射
TYPE_ICONS = {
    "看图判断题": "❓", "看图选择题": "🖼️", "图片排序题": "🔢",
    "听录音选择题": "🎧", "图片匹配题": "🖇️", "问答匹配题": "❔",
    "选词填空题": "📝", "阅读判断题": "✓✗", "句子匹配题": "⇄",
    "阅读理解题": "📖", "连词成句": "✍️", "根据拼音写汉字": "汉字",
    "情景对话题": "💬", "长文本理解题": "📚", "病句选择题": "⚠️"
}

QUESTION_TYPE_DESCRIPTIONS = {
    # 听力题型
    "听力看图判断题": "根据听到的短语，判断图片展示的对错（输出格式需包含语音文本和图片描述）",
    "看图选择题": "根据听到的句子，从N张图片中选出对应的图片（需生成多个图片描述）",
    "图片排序题": "N个对话对应N张图片，听对话选择正确的图片顺序",
    "听录音选择题": "根据录音内容选择正确答案（需生成问题和选项）",
    "文字判断题": "根据听到的对话，判断文字句子与对话内容是否一致（对/错）",
    "听短文选择题": "听短文后回答问题，选择正确答案",

    # 阅读题型
    "阅读看图判断题": "判断图片和词语表达意思是否一致（需生成图片描述和判断语句）",
    "图片匹配题": "N个句子对应N个图片，根据句子内容匹配正确图片",
    "问答匹配题": "根据问句选出对应的回答（需生成多个问答对）",
    "选词填空题": "N个句子和N个选项，选择合适的词语填空",
    "阅读判断题": "根据短句判断指定句子的对错（需用※标记目标句）",
    "句子匹配题": "N个句子和N个选项，选择正确的上下文衔接句",
    "阅读理解题": "阅读长句子后选择正确答案",
    "句子排序题": "将N个乱序句子排列成通顺的段落",
    "短文选词填空题": "阅读短文后选择正确的词语填空",
    "长文本理解题": "阅读长文本后选择与内容一致的选项",
    "阅读文章选择题": "阅读长对话/文本后回答问题（阅读理解题型）",
    "病句选择题": "从N个句子中选出有语病的一项",
    "短文选句填空题": "阅读长文本后选择正确句子填入空缺处",
    "文章选择题": "阅读文章，根据文章内容选择正确答案",

    # 写作题型
    "连词成句": "将给定的词语组合成通顺的句子",
    "根据拼音写汉字": "根据拼音写出正确的汉字",

    # 对话题型
    "情景对话题": "生成2-3轮自然对话，填空在关键交际用语位置"
}

# 详细题型配置
DETAILED_QUESTION_CONFIG = {
    "HSK1": {
        "听力": {
            "听力看图判断题": {
                "require_audio": True,
                "require_image": True,
                "audio_content": "与图片内容一致的简单描述",
                "min_words": 10,
                "max_options": 2,
                "vocab_level": 1,  # 使用数值引用 HSK_WEIGHT_CONFIG 中的配置
                "vocab_weight_mode": True  # 启用权重模式的标志
            },
            "看图选择题": {
                "require_audio": True,
                "require_image": True,
                "audio_content": "描述某一物品或场景的简短句子",
                "min_words": 10,
                "max_options": 3,
                "vocab_level": 1,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "请选择与音频描述一致的图片",
                "option_type": "image",  # 指定选项类型为图片
                "options_per_row": 3  # 每行显示的选项数量
            },
            "图片排序题": {
                "require_audio": True,
                "require_image": True,
                "audio_content": "描述图片的简单对话",
                "min_words": 30,
                "max_options": 5,
                "vocab_level": 1,
                "show_pinyin": False,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "请根据听到的对话，将图片按正确顺序排列",
                "explanation_format": "答案解析：{explanation}",
                "options_format": "{label}. {option_text}",
                "display_style": "audio_first"
            },
            "听录音选择题": {
                "require_audio": True,
                "audio_content": "与选项相关的问题",
                "min_words": 10,
                "max_options": 3,
                "vocab_level": 1,
                "vocab_weight_mode": True,  # 启用权重模式
            },
        },

        "阅读": {
            "阅读看图判断题": {
                "require_audio": False,  # 阅读题中的看图判断题不需要音频
                "require_image": True,
                "min_words": 15,
                "max_options": 2,
                "vocab_level": 1,
                "vocab_weight_mode": True,  # 启用权重模式
                "sentence_structure": "简单动词或名词",
                # "question_format": "图片显示的是[物品名称]，对还是错？",  # 问题格式
                "generate_contrast": True  # 新增标志，表示需要生成对比内容
            },
            "图片匹配题": {
                "require_audio": False,
                "require_image": True,
                "min_words": 15,
                "max_options": 5,
                "vocab_level": 1,
                "vocab_weight_mode": True,  # 启用权重模式
            },
            "问答匹配题": {
                "require_audio": False,
                "require_image": False,
                "audio_content": "多个问题的文本",
                "min_questions": 5,
                "max_questions": 5,
                "min_options": 5,
                "max_options": 5,
                "min_words": 20,
                "vocab_level": 1,
                "vocab_weight_mode": True,  # 启用权重模式
                "show_pinyin": True,  # 显示拼音
                "options_format": "A. 选项内容(拼音)",  # 选项格式
                "question_format": "{index}. {question_text}",  # 问题格式
                "options": ["A", "B", "C", "D", "E", "F", "G"]  # 选项标识
            },
            "选词填空题":
                {
                    "show_pinyin": True,  # 是否显示拼音
                    "options_per_question": 5,  # 固定5个选项
                    "max_questions": 5,  # 最多5道题
                    "max_options": 5,
                    "min_words": 20,
                    "vocab_level": 1,  # 对应HSK等级
                    "vocab_weight_mode": True,  # 启用权重模式
                }
        },
    },
    "HSK2": {
        "听力": {
            "听力看图判断题": {
                "require_audio": True,
                "require_image": True,
                "audio_content": "与图片内容一致的描述，包含一些动作或状态",
                "min_words": 30,
                "max_options": 2,
                "vocab_level": 2,
                "vocab_weight_mode": True,  # 启用权重模式
            },
            "图片排序题": {
                "require_audio": True,
                "require_image": True,
                "audio_content": "描述图片顺序的对话",
                "min_words": 60,
                "max_options": 5,
                "vocab_level": 2,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "请根据听到的对话，将图片按正确顺序排列",
                "explanation_format": "答案解析：{explanation}",
                "options_format": "{label}. {option_text}",
                "display_style": "audio_first"
            },
            "听对话选择题": {
                "require_audio": True,
                "audio_content": "与选项相关的问题",
                "min_words": 40,
                "max_options": 3,
                "vocab_level": 2,
                "vocab_weight_mode": True,  # 启用权重模式
            },
        },
        "阅读": {
            "图片匹配题": {
                "require_audio": False,
                "require_image": True,
                "min_words": 25,
                "max_options": 5,
                "vocab_level": 2,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_content": "根据给出的句子，从选项中选择与之匹配的图片描述",
                "show_pinyin": True,
                "options_format": "{label}. {option_text}"
            },
            "选词填空题": {
                "show_pinyin": False,  # 是否显示拼音
                "options_per_question": 5,  # 固定5个选项
                "max_questions": 5,  # 最多5道题
                "max_options": 5,
                "min_words": 50,
                "vocab_level": 2,  # 对应HSK等级
                "vocab_weight_mode": True,  # 启用权重模式
            },
            "阅读判断题": {
                "require_audio": False,
                "require_image": False,
                "min_words": 100,
                "max_words": 200,
                "vocab_level": 2,
                "vocab_weight_mode": True,  # 启用权重模式
                "show_pinyin": True,  # 显示拼音
                "max_options": 2,
                "question_format": "根据短文内容，判断下列陈述是否正确：",
                "explanation_format": "答案解析：{explanation}"
            },
            "句子匹配题": {
                "require_audio": False,
                "require_image": False,
                "min_sentences": 4,
                "max_sentences": 8,
                "min_options": 5,
                "max_options": 5,
                "min_words": 40,
                "vocab_level": 2,
                "vocab_weight_mode": True,  # 启用权重模式
                "show_pinyin": True,  # 显示拼音
                "options_format": "{label}. {option_text}",  # 选项格式
                "question_format": "为下列句子选择最合适的答句：",
                "explanation_format": "答案解析：{explanation}"
            }
        }
    },
    "HSK3": {
        "听力": {
            "文字判断题": {
                "require_audio": True,
                "require_image": False,
                "audio_content": "一段包含描述的文本和需要判断的目标句子（用※标记）",
                "min_words": 40,
                "max_options": 2,
                "vocab_level": 3,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "根据听到的内容，判断句子是否正确",
                "target_sentence_marker": "※",  # 标记目标句子的符号
                "options": ["对", "错"]  # 固定选项
            },
            "图片排序题": {
                "require_audio": True,
                "require_image": True,
                "audio_content": "描述图片顺序的对话",
                "min_words": 100,
                "max_options": 5,
                "vocab_level": 3,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "请根据听到的对话，将图片按正确顺序排列",
                "explanation_format": "答案解析：{explanation}",
                "options_format": "{label}. {option_text}",
                "display_style": "audio_first"
            },
            "听对话选择题": {
                "require_audio": True,
                "audio_content": "与选项相关的长对话",
                "min_words": 80,
                "max_options": 3,
                "vocab_level": 3,
                "vocab_weight_mode": True,  # 启用权重模式
            },
        },
        "阅读": {
            "阅读理解题": {
                "require_audio": False,
                "require_image": False,
                "min_paragraphs": 2,
                "max_paragraphs": 4,
                "min_words": 80,
                "max_options": 3,
                "show_pinyin": False,  # 不显示拼音
                "vocab_level": 3,  # 使用数值引用权重配置
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "根据短文内容，回答问题：",
                "explanation_format": "答案解析：{explanation}",
                "options_format": "{label}. {option_text}",
                "display_style": "paragraph_first"  # 先显示文章，再显示问题
            },
            "句子匹配题": {
                "require_audio": False,
                "require_image": False,
                "min_sentences": 6,
                "max_sentences": 8,
                "min_options": 5,
                "max_options": 5,
                "min_words": 150,
                "vocab_level": 3,
                "vocab_weight_mode": True,  # 启用权重模式
                "show_pinyin": False,  # 显示拼音
                "options_format": "{label}. {option_text}",  # 选项格式
                "question_format": "为下列句子选择最合适的答句：",
                "explanation_format": "答案解析：{explanation}"
            },
            "选词填空题": {
                "show_pinyin": True,  # 是否显示拼音
                "options_per_question": 5,  # 固定5个选项
                "max_questions": 5,  # 最多5道题
                "max_options": 5,
                "min_words": 100,
                "vocab_level": 3,  # 对应HSK等级
                "vocab_weight_mode": True,  # 启用权重模式
            },
        },
        "写作": {
            "连词成句": {
                "require_audio": False,
                "require_image": False,
                "min_words_count": 8,  # 词语最少数量
                "max_words_count": 10,  # 词语最大数量
                "min_sentence_length": 20,  # 连成句子的最少长度
                "min_words": 150,
                'max_options': 6,
                "vocab_level": "3",
                "show_pinyin": False,  #
                "question_format": "请将下列词语连成一个完整的句子：",
                "explanation_format": "答案解析：{explanation}",
                "options_format": "{label}. {option_text}"
            }
        }
    },
    "HSK4": {
        "听力": {
            "文字判断题": {
                "require_audio": True,
                "require_image": False,
                "audio_content": "一段包含描述的文本和需要判断的目标句子（用※标记）",
                "min_words": 40,
                "max_options": 2,
                "vocab_level": 4,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "根据听到的内容，判断句子是否正确",
                "target_sentence_marker": "※",  # 标记目标句子的符号
                "options": ["对", "错"]  # 固定选项
            },
            "听对话选择题4": {
                "require_audio": True,
                "audio_content": "与选项相关的问题",
                "min_words": 80,
                "max_options": 4,
                "vocab_level": 4,
                "vocab_weight_mode": True,  # 启用权重模式
            },
            "听对话选择题1v2": {
                "require_audio": True,
                "require_image": False,
                "audio_content": "一段对话材料，随后有2 - 3道选择题",
                "min_words": 100,
                "max_options": 4,
                "vocab_level": 4,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_count": [2, 3],  # 题目数量范围
                "question_audio_enabled": True,
                "show_dialogue_text": False,
                "question_format": "题目{index}: {question_text}",
                "options_format": "{label}. {option_text}",
                "display_style": "material_first"  # 先显示材料，再显示题目
            },

        },
        "阅读": {
            "选词填空题": {
                "require_audio": False,
                "require_image": False,
                "min_words": 150,
                "max_options": 5,
                "vocab_level": 4,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_content": "给出若干句子，每个句子中有一处空缺，从给定的选项中选择合适的词语填空",
                "display_format": "sentence_first"
            },
            "阅读理解题1v2": {
                "require_audio": False,
                "require_image": False,
                "min_questions": 2,
                "max_questions": 2,
                "max_passage_length": 200,
                "min_words": 180,
                "max_options": 4,
                "show_pinyin": False,  # 不显示拼音
                "vocab_level": 4,  # 使用数值引用权重配置
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "根据短文内容，回答问题：",
                "explanation_format": "答案解析：{explanation}",
                "options_format": "{label}. {option_text}",
                "display_style": "paragraph_first"  # 先显示文章，再显示问题
            },
            "句子排序题": {
                "require_audio": False,
                "require_image": False,
                "min_sentences": 3,  # 最少句子数（必填）
                "max_sentences": 5,  # 最多句子数（必填）
                "min_options": 3,
                "max_options": 5,
                "min_words": 80,
                "vocab_level": 4,  # 词汇等级
                "question_content": "将下列句子排列成一段通顺的话",
                "explanation_format": "正确顺序：{correct_order}。解析：{explanation}",
                "sort_hint": "注意逻辑关系（如总分、因果、时间顺序等）"
            }

        }

    },
    "HSK5": {
        "听力": {
            "听对话选择题5": {
                "require_audio": True,
                "audio_content": "与选项相关的问题",
                "min_words": 150,
                "max_options": 4,
                "vocab_level": 5,
                "vocab_weight_mode": True,  # 启用权重模式
            },
            "听对话选择题1v3": {
                "require_audio": True,
                "require_image": False,
                "audio_content": "一段对话材料，随后有3 - 4道选择题",
                "min_words": 200,
                "max_options": 4,
                "vocab_level": 5,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_count": [3, 4],  # 题目数量范围
                "question_audio_enabled": True,
                "show_dialogue_text": False,
                "question_format": "题目{index}: {question_text}",
                "options_format": "{label}. {option_text}",
                "display_style": "material_first"  # 先显示材料，再显示题目
            },

        },
        "阅读": {
            "短文选词填空题5": {
                "require_audio": False,
                "require_image": False,
                "max_options": 4,
                "min_words": 200,
                "vocab_level": 5,  # 词汇等级
                "question_content": "从选项中选择合适的词填入短文空格",
                "gap_format": "（{gap_number}）",  # 空格格式
                "options_per_gap": 4,  # 每个空位的选项数
                "explanation_format": "正确答案：{answer}。解析：{explanation}"
            },
            "阅读文章选择题": {
                "require_audio": False,
                "require_image": False,
                "min_questions": 4,  # 最少问题数
                "max_questions": 5,  # 最多问题数
                "max_options": 4,
                "min_words": 350,
                "vocab_level": 5,  # 词库等级（需匹配HSK词库）
                "question_types": ["词语理解", "细节理解", "推理判断", "标题归纳"],  # 问题类型
                "explanation_format": "解析：{explanation}",
                "options_per_question": 4,  # 每题选项数
            },
            "长文本理解题": {
                "question_format": "根据短文内容，选择正确答案：",
                "options_format": "{label}. {option_text}",
                "show_explanation": True,
                "max_options": 4,
                "min_words": 150,
                "vocab_level": 5
            }
        }
    },
    "HSK6": {
        "听力": {
            "听对话选择题6": {
                "require_audio": True,
                "audio_content": "与选项相关的问题",
                "min_words": 200,
                "max_options": 4,
                "vocab_level": 6,
                "vocab_weight_mode": True,  # 启用权重模式
            },
            "听对话选择题1v5": {
                "require_audio": True,
                "require_image": False,
                "audio_content": "一段对话材料，随后有4 - 5道选择题",
                "min_words": 500,
                "max_options": 4,
                "vocab_level": 6,
                "vocab_weight_mode": True,  # 启用权重模式
                "question_count": [4, 6],  # 题目数量范围
                "question_audio_enabled": True,
                "show_dialogue_text": False,
                "question_format": "题目{index}: {question_text}",
                "options_format": "{label}. {option_text}",
                "display_style": "material_first"  # 先显示材料，再显示题目
            },
            "听短文选择题": {
                "require_audio": True,
                "require_image": False,
                "min_words": 500,
                "max_options": 4,
                "vocab_level": 6,
                "audio_content": "包含校园生活、日常对话等场景",  # 添加这一行
                "vocab_weight_mode": True,  # 启用权重模式
                "question_format": "题目{index}: {question_text}",
                "options_format": "{label}. {option_text}",
                "display_style": "material_first"  # 先显示材料，再显示题目
            }

        },
        "阅读": {
            "短文选词填空题6": {
                "require_audio": False,
                "require_image": False,
                "max_options": 4,
                "min_words": 550,
                "vocab_level": 6,  # 词汇等级
                "question_content": "从选项中选择合适的词填入短文空格",
                "min_gaps": 3,  # 最少空位数
                "max_gaps": 5,  # 最多空位数
                "gap_format": "______",  # 空格格式
                "options_per_gap": 4,  # 每个空位的选项数
                "explanation_format": "正确答案：{answer}。解析：{explanation}"
            },
            "短文选句填空题": {
                "min_gaps": 5,  # 最少空位数
                "max_gaps": 5,  # 最多空位数
                "gap_format": "__{gap_number}__",  # 空位显示格式（含序号）
                "min_words": 500,
                "max_options": 5,
                "question_format": "请从选项中为短文中的空格选择最恰当的句子：",
                "options_format": "{label}. {option_text}",
                "show_pinyin": False,
                "show_explanation": True,
                "vocab_level": 6,
                "options": ["A", "B", "C", "D", "E"]
            },
            "病句选择题": {
                "min_questions": 1,
                "max_questions": 5,
                "vocab_level": 6,
                "min_words": 300,
                "max_options": 4,
                "question_format": "选出没有语病的一项：",
                "options_format": "{label}. {sentence}",
                "show_explanation": True,
                "error_types": ["逻辑错误", "歧义", "赘余", "关联词语不当", "语序不当", "搭配不当", "成分残缺", "句式杂糅"],
                "max_sentences": 4
            },
            "文章选择题": {
                "min_questions": 4,  # 最少题目数
                "max_questions": 4,  # 最多题目数
                "question_format": "根据文章内容，回答问题：",  # 问题段落标题
                "min_words": 500,
                "max_options": 4,
                "vocab_level": 6,
                "options_per_question": 4,  # 每题选项数（示例中为4，可根据需求调整）
                "explanation_format": "第 {question_id} 题解析：正确答案为 {answer}。原文提到 {explanation_key}，因此选项 {answer} 符合文意。",
                # 解析模板
                "show_explanation": True,  # 是否显示解析
                "answer_position": "end",  # 答案位置（"end"表示在选项后，可按需调整）
            }
        }
    },
}

# ========== 听力语速设置 ==========
HSK_SPEECH_RATE = {
    "HSK1": "-50%",
    "HSK2": "-40%",
    "HSK3": "-25%",
    "HSK4": "-15%",
    "HSK5": "-5%",
    "HSK6": "+0%"  # 正常语速
}

# 添加 HSK 词库加载逻辑
HSK_WORDS = {
    "HSK_1": set(json.load(open("处理json文件/1_converted.json", encoding='utf-8')))
    if os.path.exists("处理json文件/1_converted.json") else set(),
    "HSK_2": set(json.load(open("处理json文件/2_converted.json", encoding='utf-8')))
    if os.path.exists("处理json文件/2_converted.json") else set(),
    "HSK_3": set(json.load(open("处理json文件/3.json", encoding='utf-8')))
    if os.path.exists("处理json文件/3.json") else set(),
    "HSK_4": set(json.load(open("处理json文件/4.json", encoding='utf-8')))
    if os.path.exists("处理json文件/4.json") else set(),
    "HSK_5": set(json.load(open("处理json文件/5.json", encoding='utf-8')))
    if os.path.exists("处理json文件/5.json") else set(),
    "HSK_6": set(json.load(open("处理json文件/6.json", encoding='utf-8')))
    if os.path.exists("处理json文件/6.json") else set(),
}

# HSK词库权重配置
HSK_WEIGHT_CONFIG = {
    1: [0.8, 0.2, 0, 0, 0, 0],  # HSK1: 80% L1, 20% L2-3
    2: [0.2, 0.65, 0.15, 0, 0, 0],  # HSK2: 20% L1以下, 65% L2, 15% L3-4
    3: [0, 0.2, 0.6, 0.2, 0, 0],  # HSK3: 20% L2以下, 60% L3, 20% L4-5
    4: [0, 0, 0.2, 0.6, 0.2, 0],  # HSK4: 20% L3以下, 60% L4, 20% L5-6
    5: [0, 0, 0, 0.2, 0.7, 0.1],  # HSK5: 20% L4以下, 70% L5, 10% L6
    6: [0, 0, 0, 0, 0.3, 0.7]  # HSK6: 30% L5以下, 70% L6
}

# 添加HSK语法逻辑
hsk1_grammar = """HSK1对应国际中文教育中文水平等级标准的一级水平。在此阶段，学习者需牢牢掌握基础词类。像方位名词，诸如 “上、下、里、外、前、后” 等，能帮助学习者准确描述物体的位置，例如 “书在桌子上” 。部分能愿动词，如 “会、能、想、要”，用于表达能力、意愿等，比如 “我会唱歌”“我想要一个苹果” 。疑问代词 “谁、什么、哪儿、多少、几”，可用于询问人、事物、地点、数量等，像 “你是谁？”“这是什么？” 。人称代词 “我、你、他、她、它、我们、你们、他们”，在日常交流中用于指代不同对象，如 “他是我的朋友” 。指示代词 “这（这儿）、那（那儿）”，用以指示近处和远处的事物，例如 “这是我的书，那是你的笔” 。基本数词 “一、二、三、四、五、六、七、八、九、十” 和量词 “个、本、条、张、只、件、块” 等，用于表示数量，像 “一个苹果、一本书、一条鱼” 。还有各类副词，程度副词如 “很、太”，可以描述程度，如 “这个苹果很甜”“天气太热了” ；范围副词 “都、也”，例如 “我们都是学生”“我也喜欢唱歌” ；时间副词 “现在、已经、马上”，如 “我现在要去学校”“我已经吃完饭了”“我马上就来” 。常见介词 “从、在、到”，如 “我从家里来”“我在学校”“我到图书馆了” 。连词 “跟、和、还是”，比如 “我跟他是朋友”“我喜欢苹果和香蕉”“你喜欢苹果还是香蕉？” 。助词 “的、地、了、吧、吗、呢”，“的” 用于修饰名词，如 “红色的苹果”；“地” 用于修饰动词，如 “慢慢地走”；“了” 可表示动作的完成或变化，如 “我吃了饭”“天气变凉了”；“吧”“吗”“呢” 用于构成疑问句，如 “你吃饭了吗？”“我们一起去吧”“你在做什么呢？”。
能运用简单短语，例如数量短语 “一个、两个” 等，能与名词搭配使用。学会基本句子成分的使用，能构造主谓句，像动词谓语句 “我吃饭”，形容词谓语句 “她很漂亮” ；非主谓句，如 “好的”“谢谢” 。以及陈述句，用来陈述事实，如 “我是中国人” ；疑问句，包含是非问句 “你是学生吗？”，特指问句 “你在哪里？” ；祈使句，用于表达请求、命令等，如 “请坐”“不要说话” ；感叹句，抒发情感，如 “好漂亮啊！” 。还要掌握 “是” 字句，用于判断和说明，如 “他是老师” ；“有” 字句，用来表示存在，如 “桌子上有一本书” ；比较句的基本用法，如 “我比你高” 。以及动作的变化态、完成态、进行态表达，比如 “我长高了（变化态）”“我写完作业了（完成态）”“我正在看电视（进行态）” 。能运用简单复句，像不用关联词语的并列复句，如 “我喜欢唱歌，我也喜欢跳舞” 。学会基本的钱数、时间表示法和多种提问方法，例如钱数 “十块钱”“五毛钱”，时间 “八点”“明天”，提问如 “现在几点了？”“你什么时候去学校？”"""
hsk2_grammar = """HSK2对应国际中文教育中文水平等级标准的二级水平。在HSK1基础上，对各类词的运用要求更加熟练。以动词为例，学习者要能更准确地运用动词的不同形式来表达不同的语义，像 “我吃了饭”（“吃” 的完成态）和 “我正在吃饭”（“吃” 的进行态），要能分清何时该用何种形式。代词方面，对指示代词 “这、那” 的指代用法理解要更深入，能在更复杂的语境中准确运用，比如 “这是我昨天买的书，那是我上周借的杂志”，明确不同时间所指事物的差异。副词的运用也更灵活，比如程度副词 “有点儿”，可以表达不太强烈的程度，“今天有点儿冷”；范围副词 “都” 在不同句式中的运用，“我们都喜欢这个电影” 和 “这些水果都很好吃”，体会其在不同主语和宾语结构中的作用。
能灵活运用更多类型的短语，如动宾短语 “看电视、打篮球”，可以更丰富地描述行为动作；偏正短语 “漂亮的花、红色的衣服”，对事物的修饰更细致。在句子构造上，对主谓句、非主谓句的运用更自如，例如主谓句中宾语可以是更复杂的名词短语，“我喜欢红色的苹果”，而非主谓句在情境对话中的使用更加自然，像 “好呀”“当然可以” 。且能使用更多复杂的句式，比如在比较句中，除了 “A 比 B + 形容词”，还涉及 “A 没有 B + 形容词” 的用法，如 “我的苹果没有你的大”，能更全面地进行比较。能更熟练运用复句，如使用 “一边……，一边……”“……，也……” 等关联词语的并列复句，“我一边听音乐，一边写作业”“我喜欢唱歌，也喜欢跳舞”，清晰地表达同时进行的动作或并列的情况。同时，在时间表示法等方面的运用也更准确和多样化，例如能准确表达 “去年、下个月、后天” 等时间概念，在句子中能正确运用，如 “我去年去了北京”“下个月我要过生日”“后天我们一起去玩吧” 。"""
hsk3_grammar = """HSK3对应国际中文教育中文水平等级标准的三级水平。学习者要进一步丰富词类的掌握，尤其是一些在特定语境和表达中常用的词。
例如，一些具有特定文化内涵的名词，像 “春节、中秋节” 等，学习者不仅要知道其含义，还要了解相关的文化背景和在句子中的运用，如 “我们每年都过春节” 。在句子层面，对句子成分的理解和运用更加深入，能理解和构造更复杂的单句和复句。除了之前的句型和句类，可能涉及一些特殊句式的变形和扩展用法，比如 “把” 字句，“我把书放在桌子上”，要理解 “把” 所强调的对象和动作的处置关系；被字句 “杯子被我打碎了”，理解动作的被动关系。在复句方面，对并列复句的运用更加灵活，还可能接触到其他类型的复句，如因果复句 “因为今天下雨，所以我没出去玩”，能理解和表达句子之间的因果逻辑关系。在动作的表达上，对动作态的理解和运用更加细腻，能准确表达动作在不同阶段的状态，比如 “我已经学了三年汉语了（完成态持续到现在）”“我正在学习汉语（进行态）”“我明天要学习汉语（将来态）” 。此外，在数的表示法、时间表示法等方面更加精准，能处理更复杂的数字和时间表达场景，如 “我坐了三个小时的车”“会议将在 2025 年 10 月 15 日上午 9 点开始” 。"""
hsk4_grammar = """HSK4 对应国际中文教育中文水平等级标准的四级水平，在此阶段，学习者需要掌握更为丰富和复杂的语法知识，以满足日常交流和一般性阅读写作的需求。
词类拓展：学习者会接触到更多高级词汇，尤其是一些抽象名词，像 “文化、思想、理论、政策” 等，要能准确理解并在句子中正确运用，例如 “我们应该尊重不同国家的文化”“他的思想很有深度” 。同时，部分动词的引申义、一词多义现象也会更多出现，如 “打” 字，在 “打电话”“打伞”“打水” 中就有不同的含义，学习者需要根据语境准确把握 。
句子结构复杂化：单句方面，除了基本的主谓宾结构，句子成分会更加多样和复杂，定语和状语的修饰层次增多。比如 “那位来自中国的年轻漂亮的女老师正在教室里认真地给学生们讲课”，其中 “那位来自中国的年轻漂亮的” 是多层定语修饰 “女老师”，“正在教室里认真地给学生们” 是多层状语修饰 “讲课” 。复句类型进一步丰富，因果复句 “因为他平时学习很努力，所以这次考试取得了优异的成绩”；转折复句 “虽然今天的工作任务很重，但是大家都没有抱怨”；假设复句 “如果明天不下雨，我们就去公园放风筝” ，学习者要能准确运用关联词语，清晰表达句子之间的逻辑关系 。
语法功能应用：在日常交流和一般性阅读写作中，学习者需要能够熟练运用各种语法结构准确表达想法和理解内容。如在描述一次旅行经历时，能正确使用过去时态和各种句式，“上个周末，我和朋友们去了杭州。我们游览了美丽的西湖，品尝了当地的特色美食，还拍了很多好看的照片” ；在阅读简单的新闻报道、故事短文时，能理解其中复杂的语法结构所传达的信息 。"""
hsk5_grammar = """HSK5 对应国际中文教育中文水平等级标准的五级水平，语法难度进一步提升，更侧重于在较为专业和复杂的场景中准确、流畅地运用语法知识。
词类深化：学习者会接触到更多具有特定文化内涵和专业领域的词汇，如历史文化领域的 “科举、丝绸之路”，经济领域的 “通货膨胀、市场经济” 。此外，一些文言词汇在固定表达或文学作品引用中频繁出现，像 “之” 在 “久而久之”“总之” 中的使用，“乎” 在 “不亦乐乎” 中的运用，学习者需要理解这些词汇在现代语境中的含义和用法 。同时，词语的搭配更加多样化和精细化，例如 “发扬” 常与 “精神、传统” 搭配，“发挥” 常与 “作用、优势” 搭配，要能准确区分和使用 。
句子结构多样化：单句结构更加复杂，可能会出现长句、难句，如 “在那座位于城市中心的、有着悠久历史和独特建筑风格的古老博物馆里，珍藏着无数见证了这座城市发展变迁的珍贵文物” 。复句类型更加丰富，多个复句嵌套的情况增多，如 “如果我们想要在激烈的市场竞争中脱颖而出，不仅需要不断创新产品和服务，而且要加强品牌建设和市场推广，然而，这一切都离不开专业的人才和充足的资金支持” 。此外，还会涉及到一些特殊句式的灵活运用，如 “是…… 的” 强调句，“他是昨天下午来的北京”，突出时间 ；“连…… 也 / 都……” 句式，“连小孩子也知道这个道理”，表示强调 。
语法功能提升：在学术交流、商务沟通等较为专业的场景中，学习者需要运用复杂的语法结构进行准确、得体的表达，如在商务谈判中，能够清晰阐述合作方案和条件，“如果贵方能够在价格上做出一定让步，并且保证产品的质量和交货期，那么我们愿意与贵方签订长期合作协议” 。在阅读专业文献、学术论文时，能理解复杂的语法结构所表达的专业内容和逻辑关系 。在篇章层面，要能够运用连接词、代词指代、重复关键词等语法手段，使段落之间过渡自然，内容连贯，如 “首先，我们对市场需求进行了深入调研；其次，根据调研结果制定了产品研发计划；最后，通过严格的测试和优化，推出了满足市场需求的新产品。这些措施有效地提高了产品的竞争力” 。"""
hsk6_grammar = """HSK6 对应国际中文教育中文水平等级标准的六级水平，是对学习者中文语法掌握的最高要求，注重在文学创作、学术研究等高层次场景中精准、灵活且富有表现力地运用语法。​
词类精通：学习者需要掌握大量的高级词汇，包括具有比喻、象征意义的词汇，如 “雨后春笋” 形容事物迅速大量地涌现出来，“铁石心肠” 表示心肠硬，不为感情所动 。同时，对一些词语的语体色彩、感情色彩把握要非常准确，如 “教诲” 多用于书面语和正式场合，“教导” 则更口语化 ；“果断” 是褒义词，“武断” 是贬义词，要能根据语境恰当使用 。此外，一些古汉语词汇和句式在文学作品、经典文献中的运用，如 “之乎者也” 在仿古表达中的使用，“亦…… 亦……” 句式，“亦余心之所善兮，虽九死其犹未悔” ，学习者需要理解并能够在适当场合引用或模仿 。
句子结构精妙化：句子结构高度复杂，常常出现多层修饰、多重嵌套的情况，如 “在那个被金色阳光温柔笼罩着的、弥漫着阵阵花香的、宁静而又美丽的小村庄里，一位白发苍苍的老妇人正坐在自家门前那棵有着粗壮枝干和茂密树叶的老槐树下，一边轻轻地摇着手中的蒲扇，一边向围坐在她身旁的孩子们讲述着那些充满传奇色彩和神秘魅力的古老故事” 。复句的运用达到炉火纯青的地步，各种逻辑关系交织，如 “倘若我们不珍惜眼前的机会，并且在遇到困难时轻易放弃，那么不仅之前的努力会付诸东流，而且未来的发展也将受到严重阻碍，然而，只要我们坚定信念，勇往直前，就有可能克服重重困难，实现最终的目标” 。同时，修辞手法与语法结构紧密结合，如排比句 “爱心是一片照射在冬日的阳光，使贫病交迫的人感到人间的温暖；爱心是一泓出现在沙漠里的泉水，使濒临绝境的人重新看到生活的希望；爱心是一首飘荡在夜空的歌谣，使孤苦无依的人获得心灵的慰藉” ，通过语法结构的巧妙安排，增强表达效果 。
语法功能高阶应用：在文学创作中，能够运用丰富多样的语法结构塑造人物形象、营造氛围、表达情感，如在小说中通过细腻的描写和独特的句式展现人物性格，“他缓缓地抬起头，眼神中透露出一丝迷茫与无奈，仿佛在黑暗中迷失了方向的孤舟，不知道该驶向何方” 。在学术研究中，准确运用复杂的语法结构进行严谨的论证和清晰的阐述，如在学术论文中，“综上所述，通过对相关数据的深入分析和研究，我们可以得出以下结论：在当前的市场环境下，企业只有不断加大研发投入，优化产品结构，并且积极拓展市场渠道，才能够在激烈的竞争中立于不败之地，然而，这一过程并非一帆风顺，还需要企业具备强大的执行力和创新能力” 。在篇章层面，能够熟练运用各种语法手段构建层次分明、逻辑严密、富有感染力的篇章，使文章主题突出，内容连贯，如在一篇论述文中，通过巧妙使用连接词、过渡句和总结句，将各个段落有机结合，“首先，从历史的角度来看，……；其次，就现实情况而言，……；最后，展望未来的发展趋势，……。由此可见，……” 。"""

# 中英文男女声映射表
VOICE_MAPPING = {
    'female': {
        'zh': 'zh-CN-XiaoxiaoNeural',
        'en': 'en-US-AriaNeural'
    },
    'male': {
        'zh': 'zh-CN-YunyangNeural',
        'en': 'en-US-DavisNeural'
    }
}


# 字数逻辑


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
1. 共生成{num_questions}道题
2. 保持题型多样性
3. 难度符合HSK{level}大纲
4. 每次启动程序生成的题目都要不一样
5. 选项要有干扰项，干扰强度随着HSK等级逐级提升
【输出格式】
{{
  "questions": [
    {{
      "type": "题型名称",
      "content": "题目内容",
      "passages": ["所需的文章或段落"],
      "questions": ["问题1", "问题2", ...],  // 新增字段
      "gaps":["第一空","第二空, ..."]
      "options": ["A", "B", ...],  // 选择题需要
      "answer": "正确答案",
      "explanation": "答案解析",  // 可选
      "audio_content": "语音内容（如果有）",
      "audio_question": "语音问题（如果有）",
      "image_description": "图片描述（如果有）",
      "sentences": ["句子1", "句子2", ...]  // 新增字段，用于存储填空题的句子
    }}
  ]

}}
【题型示例】
{json.dumps(relevant_examples, ensure_ascii=False, indent=2)}
"""


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
            "audio_content": "昨天晚上雨下得很大，城市的街道像是被洗过一样，变得非常干净。昨天晚上下了大雪",
            "target_sentence": "昨天晚上下了大雪",
            "answer": "错"},
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
            "answer": "B"
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
                "A. 图片的描述是，一个女人抱着一堆报纸",
                "B. 图片描述是一些切好的西瓜",
                "C. 图片描述是一个女孩向男孩请教问题",
                "D. 图片描述是一个男人举着一台笔记本电脑",
                "E. 图片描述是一个快递员送货上门"
            ],
            "answer": ["A", "E", "D", "C", "B"]
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
    """展示题型示例"""
    img_path = f"images/{level}_{category}_{type_name}.jpg"
    try:
        with st.expander(f"{TYPE_ICONS.get(type_name, '')} {type_name} ", expanded=False):
            st.image(img_path, use_container_width=True)
    except:
        st.warning("示例图片加载失败")


def main():
    st.set_page_config(layout="wide")
    st.title("📚 HSK智能题库生成系统")
    init_sample_images()

    # ===== 左侧控制面板 =====
    with st.sidebar:
        st.header("⚙️ 题目设置")

        # 1. 选择HSK级别
        level = st.selectbox(
            "选择HSK级别",
            list(QUESTION_TYPES.keys()),
            index=0  # 默认HSK1
        )

        # 2. 选择题型分类
        category = st.selectbox(
            "选择题型分类",
            list(QUESTION_TYPES[level].keys())
        )

        # 3. 选择具体题型（多选）
        st.markdown("**选择具体题型：**")
        selected_types = []
        for type_name in QUESTION_TYPES[level][category]:
            cols = st.columns([1, 4])
            with cols[0]:
                if st.checkbox("", key=f"check_{type_name}"):
                    selected_types.append(type_name)
            with cols[1]:
                show_question_type_example(level, category, type_name)

        # 4. 题目数量控制
        num_questions = st.slider(
            "题目数量",
            min_value=1,
            max_value=20,
            value=5,
            help="每组生成的题目数量"
        )

        # 5. 高级选项（HSK5-6）
        if level in ["HSK5", "HSK6"]:
            st.markdown("**高级设置：**")
            use_advanced_vocab = st.checkbox("使用高级词汇", True)
            include_culture = st.checkbox("包含文化知识点", False)

    # ===== 主内容区域 =====
    if not selected_types:
        st.warning("请至少选择一种题型")
        return

    if st.button("🚀 生成题目", type="primary"):
        with st.spinner(f"正在生成{level} {category}题目..."):
            # 1. 生成Prompt
            prompt = generate_prompt(level, category, selected_types, num_questions)

            # 2. 调用API
            response = get_completion(prompt)

            # 3. 处理结果
            if response:
                data = clean_json_response(response)
                if data and "questions" in data:
                    st.session_state.questions = data["questions"]
                    st.session_state.level = level
                    st.session_state.category = category
                    display_questions(data["questions"], level, category)
                else:
                    st.error("生成失败，请检查API返回格式")
                    with st.expander("查看原始响应"):
                        st.code(response)
    elif 'questions' in st.session_state and 'level' in st.session_state and 'category' in st.session_state:
        display_questions(st.session_state.questions, st.session_state.level, st.session_state.category)


# 题型处理器 - 策略模式实现
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)


def handle_look_and_judge1(q, level, category, i):
    """处理看图判断题（支持男女声双语音播报）"""
    # 获取该题型的详细配置
    global adjusted_audio_text
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})

    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))  # 获取HSK数字等级

    st.write("调试：短文选词填空题数据结构 =", q)

    female_audio = None
    male_audio = None

    try:
        # 处理听力部分
        if type_config.get("require_audio", True):
            audio_text = q.get("audio_content", q["content"])

            # 根据HSK等级调整听力内容词汇
            adjusted_audio_text = adjust_text_by_hsk(audio_text, hsk_num)

            st.markdown("🎧 **点击播放录音题内容：**")

            # 生成带路径的临时音频文件
            female_audio = os.path.join(TEMP_DIR, f"temp_female_{uuid.uuid4().hex}.mp3")
            male_audio = os.path.join(TEMP_DIR, f"temp_male_{uuid.uuid4().hex}.mp3")

            # 分别处理男女声音频生成，避免一个失败影响另一个
            try:
                # 异步生成女声音频
                asyncio.run(text_to_speech(adjusted_audio_text, female_audio, level, voice='female'))
            except Exception as e:
                st.error(f"女声音频生成失败：{str(e)}")
                female_audio = None

            try:
                # 异步生成男声音频
                asyncio.run(text_to_speech(adjusted_audio_text, male_audio, level, voice='male'))
            except Exception as e:
                st.error(f"男声音频生成失败：{str(e)}")
                male_audio = None

            # 播放音频（仅当音频文件存在时）
            if female_audio and os.path.exists(female_audio):
                st.markdown("👩 **女声朗读：**")
                play_audio_in_streamlit(female_audio)

                # 添加小延迟，确保音频播放完成
                time.sleep(1)

            if male_audio and os.path.exists(male_audio):
                st.markdown("👨 **男声朗读：**")
                play_audio_in_streamlit(male_audio)

        # 处理图片部分
        if type_config.get("require_image", True):
            image_desc = q.get("image_description", q["content"])
            st.markdown("🖼️ **根据描述生成图像：**")
            img_bytes = generate_image_from_text(image_desc)
            if img_bytes:
                st.image(img_bytes, width=200)

        # 显示选项
        if q.get("options"):
            # 根据HSK等级调整选项词汇
            adjusted_options = [adjust_text_by_hsk(option, hsk_num) for option in q["options"]]

            if f'answer_{i}' not in st.session_state:
                st.session_state[f'answer_{i}'] = None

            # 修复了之前代码中的语法错误（将中文逗号改为英文逗号）
            selected_option = st.radio(
                "请选择正确的答案：",
                adjusted_options,
                index=adjusted_options.index(st.session_state[f'answer_{i}'])
                if st.session_state[f'answer_{i}'] in adjusted_options else 0,
                key=f"options_{i}"
            )

            st.session_state[f'answer_{i}'] = selected_option

    finally:
        # 安全地清理临时文件
        for file in [female_audio, male_audio]:
            if file and os.path.exists(file):
                try:
                    os.remove(file)
                    st.debug(f"已成功删除临时文件: {file}")
                except Exception as e:
                    st.warning("")


def handle_look_and_judge2(q, level, category, i):
    """处理阅读看图判断题"""
    # 获取该题型的详细配置
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})

    # 处理听力部分

    # 处理图片部分
    if type_config.get("require_image", True):
        image_desc = q.get("image_description", q["content"])
        st.markdown("🖼️ **根据描述生成图像：**")
        img_bytes = generate_image_from_text(image_desc)
        if img_bytes:
            st.image(img_bytes, width=200)

        # 显示题目内容
        # st.markdown(f"**题目描述：** {q.get('content', '')}")

        # 显示问题
        if q.get("question"):
            st.markdown(f"**问题：** {q['question']}")

    # 显示选项
    if q.get("options"):
        if f'answer_{i}' not in st.session_state:
            st.session_state[f'answer_{i}'] = None

        selected_option = st.radio("请选择正确的答案：",
                                   q["options"],
                                   index=q["options"].index(st.session_state[f'answer_{i}']) if
                                   st.session_state[f'answer_{i}'] in q["options"] else 0,
                                   key=f"options_{i}")

        st.session_state[f'answer_{i}'] = selected_option


def handle_look_and_choice(q, level, category, i):
    """处理看图选择题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    # 处理听力部分
    if type_config.get("require_audio", True):
        audio_text = q.get("audio_content", q["content"])
        adjusted_audio_text = adjust_text_by_hsk(audio_text, hsk_num)

        st.markdown("🎧 **点击播放录音：**")
        temp_audio = f"temp_{uuid.uuid4().hex}.mp3"
        try:
            asyncio.run(text_to_speech(adjusted_audio_text, temp_audio, level))
            play_audio_in_streamlit(temp_audio)
        finally:
            if os.path.exists(temp_audio):
                os.remove(temp_audio)

    # 处理图片部分
    if type_config.get("require_image", True):
        st.markdown("🖼️ **请选择对应的图片：**")

        # 处理选项图片
        option_images = q.get("option_images", [])
        if option_images:
            cols = st.columns(len(option_images))
            for j, img_desc in enumerate(option_images):
                img_bytes = generate_image_from_text(img_desc)
                if img_bytes:
                    cols[j].image(img_bytes, width=150)
                    cols[j].radio(f"选项{chr(65 + j)}",
                                  [f"选项{chr(65 + j)}"],
                                  key=f"img_option_{i}_{j}")

    # 显示问题
    if q.get("question"):
        adjusted_question = adjust_text_by_hsk(q["question"], hsk_num)
        st.markdown(f"**问题：** {adjusted_question}")

    # 显示文本选项（如果有）
    if q.get("options"):
        adjusted_options = [f"{chr(65 + j)}. {adjust_text_by_hsk(option, hsk_num)}"
                            for j, option in enumerate(q["options"])]

        if f'answer_{i}' not in st.session_state:
            st.session_state[f'answer_{i}'] = None

        selected_option = st.radio(
            "请选择正确的答案：",
            adjusted_options,
            index=adjusted_options.index(f"{q.get('answer', 'A')}. {q.get('options', [''])[0]}")
            if f"{q.get('answer', 'A')}. {q.get('options', [''])[0]}" in adjusted_options else 0,
            key=f"options_{i}"
        )

        st.session_state[f'answer_{i}'] = selected_option.split('.')[0].strip()


def handle_image_sorting(q, level, category, i):
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    dialogues = q.get("dialogues", [])
    options = q.get("options", [])
    answers = q.get("answers", [])

    # 尝试从不同字段获取对话
    dialogues = q.get("dialogues", [])

    # 如果dialogues为空，尝试其他可能的字段
    if not dialogues:
        dialogues = q.get("sentences", [])  # 尝试sentences字段

    if not dialogues:
        # 尝试从audio_content字段分割对话（假设用|分隔）
        audio_content = q.get("audio_content", "")
        if audio_content:
            dialogues = audio_content.split("|")
            dialogues = [d.strip() for d in dialogues if d.strip()]  # 过滤空对话

    # 如果还是没有对话，尝试检查单独的对话字段（如dialogue1, dialogue2...）
    if not dialogues:
        dialogues = []
        for j in range(1, 6):  # 尝试dialogue1到dialogue5
            key = f"dialogue{j}"
            if key in q and q[key]:
                dialogues.append(q[key])

    # 验证对话数量
    if len(dialogues) != 5:
        st.error(f"对话数量不正确，需要5段对话，但实际有 {len(dialogues)} 段。请检查数据格式。")
        st.json(q)  # 显示原始数据，帮助调试
        return

    st.markdown(f"### {type_config.get('question_format', '请根据听到的五段对话，将图片按对应顺序排列')}")

    # 播放五段对话录音
    st.markdown("### 听力对话")
    for j, dialogue in enumerate(dialogues):
        adjusted_dialogue = adjust_text_by_hsk(dialogue, hsk_num)
        audio_path = f"temp_{uuid.uuid4().hex}.mp3"
        try:
            asyncio.run(text_to_speech(adjusted_dialogue, audio_path, level))
            st.markdown(f"**对话 {j + 1}：**")
            play_audio_in_streamlit(audio_path)
        except Exception as e:
            st.error(f"对话 {j + 1} 音频生成失败: {str(e)}")
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    # 显示选项
    st.markdown("### 选项")
    cols = st.columns(len(options))
    for k, option in enumerate(options):
        img_bytes = generate_image_from_text(option)
        if img_bytes:
            cols[k].image(img_bytes, caption=f"选项 {chr(65 + k)}", use_container_width=True)
        else:
            cols[k].markdown(f"{chr(65 + k)}. {option}")

    # 用户选择区域
    selected_order = []
    for j in range(len(dialogues)):
        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = ""

        selected_option = st.selectbox(
            f"请为对话 {j + 1} 选择对应的图片选项：",
            [chr(65 + k) for k in range(len(options))],
            index=next(
                (idx for idx, opt in enumerate([chr(65 + k) for k in range(len(options))])
                 if opt == st.session_state[answer_key]),
                0
            ),
            key=f"sorting_{i}_{j}"
        )
        selected_order.append(selected_option)
        st.session_state[answer_key] = selected_option

    # 显示答案与解析
    with st.expander("查看答案与解析", expanded=False):
        st.success(f"正确的图片顺序：{' -> '.join(answers)}")
        explanation = q.get("explanations", [""])
        st.info(type_config.get('explanation_format', '').format(explanation=explanation))


def handle_listening(q, level, category, i):
    """处理听力选择题（支持男女声双语音播报）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write("调试：阅读选择题数据结构 =", q)

    # 提取题目信息
    audio_content = q.get("audio_content", "")
    question = q.get("audio_question", "")
    options = q.get("options", [])

    # 调整词汇
    adjusted_audio_content = adjust_text_by_hsk(audio_content, hsk_num)
    adjusted_question = adjust_text_by_hsk(question, hsk_num)
    adjusted_options = [adjust_text_by_hsk(option, hsk_num) for option in options]

    # 生成男女声的临时音频文件
    female_audio = f"temp_female_{uuid.uuid4().hex}.mp3"
    question_audio1 = f"temp_female_{uuid.uuid4().hex}.mp3"
    male_audio = f"temp_male_{uuid.uuid4().hex}.mp3"
    question_audio2 = f"temp_male_{uuid.uuid4().hex}.mp3"
    # 播放录音
    st.markdown("🎧 **听力内容：**")

    try:
        # 异步生成女声音频
        asyncio.run(text_to_speech(adjusted_audio_content, female_audio, level, voice='female'))
        # 异步生成男声音频
        asyncio.run(text_to_speech(adjusted_audio_content, male_audio, level, voice='male'))

        asyncio.run(text_to_speech(adjusted_question, question_audio1, level, voice='female'))

        asyncio.run(text_to_speech(adjusted_question, question_audio2, level, voice='male'))

        # 直接显示音频播放器
        st.markdown("👩 **女声朗读：**")
        play_audio_in_streamlit(female_audio)

        st.markdown("**问题：**")
        play_audio_in_streamlit(question_audio1)

        st.markdown("👨 **男声朗读：**")
        play_audio_in_streamlit(male_audio)

        st.markdown("**问题：**")
        play_audio_in_streamlit(question_audio2)



    except Exception as e:
        st.error(f"生成或播放录音时出错: {str(e)}")
    finally:
        # 使用st.session_state跟踪文件，确保在会话结束时清理
        if 'temp_files' not in st.session_state:
            st.session_state.temp_files = []
        st.session_state.temp_files.extend([female_audio, male_audio])

    # 显示问题和选项
    # st.markdown(f"**问题：** {adjusted_question}")

    if f'answer_{i}' not in st.session_state:
        st.session_state[f'answer_{i}'] = None

    option_labels = [f"{chr(65 + j)}. {option}" for j, option in enumerate(adjusted_options)]

    selected_option = st.radio(
        "请选择正确的答案：",
        option_labels,
        index=option_labels.index(st.session_state[f'answer_{i}'])
        if st.session_state[f'answer_{i}'] in option_labels else 0,
        key=f"listening_options_{i}"
    )

    st.session_state[f'answer_{i}'] = selected_option


def handle_fill_in_the_blank(q, level, category, i):
    """处理选词填空题（支持拼音显示和多题一次性展示）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))
    show_pinyin = type_config.get("show_pinyin")
    max_questions = type_config.get("max_questions", 5)

    st.write("调试：阅读选择题数据结构 =", q)

    # ------------------------------
    # 1. 数据校验
    # ------------------------------
    sentences = q.get("sentences", [])
    options = q.get("options", [])

    if len(sentences) == 0:
        st.error("错误：请至少添加1道题")
        return

    if len(sentences) > max_questions:
        st.warning(f"警告：最多支持{max_questions}道题，已截断多余题目")
        sentences = sentences[:max_questions]

    if len(options) != 5:  # 固定5个选项
        st.error("错误：必须包含5个选项（A-E）")
        return

    # ------------------------------
    # 2. 文本处理（拼音和难度调整）
    # ------------------------------
    adjusted_sentences = []
    for sentence in sentences:
        # 调整词汇难度（示例逻辑，需根据实际实现）
        adjusted_sentence = adjust_text_by_hsk(sentence, hsk_num)

        # 生成带拼音的句子（可选）
        if show_pinyin:
            adjusted_text = adjust_text_by_hsk(sentence, hsk_num)
            pinyin_text = add_pinyin(adjusted_text) if type_config.get("show_pinyin", True) else adjusted_text
            adjusted_sentences.append(f"{adjusted_sentence} （拼音：{pinyin_text}）")
        else:
            adjusted_sentences.append(adjusted_sentence)

    adjusted_options = [adjust_text_by_hsk(opt, hsk_num) for opt in options]

    # ------------------------------
    # 3. 显示题目（先显示所有句子，再统一显示选项）
    # ------------------------------
    st.markdown(f"### HSK{hsk_num} 选词填空题（共{len(sentences)}道题）")

    # 显示所有句子
    for idx, sentence in enumerate(adjusted_sentences, 1):
        st.markdown(f"**第{idx}题：** {sentence}")

    # 显示选项（一次性展示5个选项）
    st.markdown("### 选项（ABCDE对应5个选项）：")
    option_labels = [f"{chr(65 + j)}. {opt}" for j, opt in enumerate(adjusted_options)]
    st.markdown("  ".join(option_labels))  # 横向显示选项

    # ------------------------------
    # 4. 答案选择（使用隐藏输入匹配选项）
    # ------------------------------
    user_answers = {}
    for idx in range(len(sentences)):
        # 每个题目使用独立的key
        key = f"fill_answer_{i}_{idx}"
        user_answer = st.text_input(
            f"请为第{idx + 1}题选择答案（输入A-E）",
            key=key,
            max_chars=1,
            placeholder="A"
        ).upper()

        # 验证答案格式
        if user_answer in ["A", "B", "C", "D", "E"]:
            user_answers[idx + 1] = user_answer  # 存储题号对应的答案
        else:
            user_answers[idx + 1] = ""  # 无效输入视为未答

    # ------------------------------
    # 5. 提交与结果验证
    # ------------------------------
    if st.button(f"提交第{i + 1}组填空题答案", key=f"submit_fill_{i}"):
        correct_count = 0
        for idx, (sentence, correct_option) in enumerate(zip(sentences, q.get("answers", []))):
            question_id = idx + 1
            user_answer = user_answers.get(question_id, "")
            correct_answer = correct_option.upper()

            with st.expander(f"第{question_id}题 结果"):
                st.markdown(f"**题目：** {sentence}")
                st.markdown(f"**你的答案：** {user_answer}")
                st.markdown(f"**正确答案：** {correct_answer} {'✅' if user_answer == correct_answer else '❌'}")

                # 显示选项对应的词语（可选）
                if user_answer:
                    selected_word = adjusted_options[ord(user_answer) - 65]  # A->0, B->1...
                    st.markdown(f"**选项含义：** {selected_word}")

        score = f"{correct_count}/{len(sentences)}"
        st.success(f"得分：{score} ({correct_count / len(sentences):.0%})")


def handle_text_judgment1(q, level, category, i):
    """处理文字判断题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    # 提取题目信息
    audio_content = q.get("audio_content", "")
    target_sentence = q.get("target_sentence", "")
    options = type_config.get("options", ["对", "错"])

    # 调整词汇
    adjusted_audio_content = adjust_text_by_hsk(audio_content, hsk_num)
    adjusted_target_sentence = adjust_text_by_hsk(target_sentence, hsk_num)

    # 播放录音
    st.markdown("🎧 **点击播放录音：**")
    temp_audio = f"temp_{uuid.uuid4().hex}.mp3"

    try:
        asyncio.run(text_to_speech(adjusted_audio_content, temp_audio, level))
        play_audio_in_streamlit(temp_audio)
    except Exception as e:
        st.error(f"生成或播放录音时出错: {str(e)}")
    finally:
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

    # 显示带标记的完整句子

    # 显示问题和需要判断的句子
    st.markdown("### 问题：")
    st.markdown(f"请判断 **※{adjusted_target_sentence}※** 是否正确")

    # 显示选项
    if f'answer_{i}' not in st.session_state:
        st.session_state[f'answer_{i}'] = None

    selected_option = st.radio(
        "请选择：",
        options,
        index=options.index(st.session_state[f'answer_{i}']) if
        st.session_state[f'answer_{i}'] in options else 0,
        key=f"judgment_options_{i}"
    )

    st.session_state[f'answer_{i}'] = selected_option


def handle_sentence_matching1(q, level, category, i):
    """处理句子匹配题（包括问答匹配题）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    # 提取题目信息
    questions = q.get("questions", [])
    options = q.get("options", [])
    answers = q.get("answers", [])

    # 调试输出
    st.write(f"处理问答匹配题 - 问题数量: {len(questions)}, 选项数量: {len(options)}")

    # 调整词汇并添加拼音
    adjusted_questions = []
    for question in questions:
        # 处理问题可能是字符串或字典的情况
        if isinstance(question, str):
            adjusted_text = adjust_text_by_hsk(question, hsk_num)
            pinyin_text = add_pinyin(adjusted_text) if type_config.get("show_pinyin", True) else adjusted_text
            adjusted_questions.append({
                "text": adjusted_text,
                "pinyin": pinyin_text,
                "index": str(len(adjusted_questions) + 1)
            })
        else:  # 字典格式
            question_text = question.get("text", "")
            adjusted_text = adjust_text_by_hsk(question_text, hsk_num)
            pinyin_text = add_pinyin(adjusted_text) if type_config.get("show_pinyin", True) else adjusted_text
            adjusted_questions.append({
                "text": adjusted_text,
                "pinyin": pinyin_text,
                "index": question.get("index", str(len(adjusted_questions) + 1))
            })

    adjusted_options = []
    for idx, option in enumerate(options):
        # 处理选项可能是字符串或字典的情况
        if isinstance(option, str):
            adjusted_text = adjust_text_by_hsk(option, hsk_num)
            pinyin_text = add_pinyin(adjusted_text) if type_config.get("show_pinyin", True) else adjusted_text
        else:  # 字典格式
            option_text = option.get("text", "")
            adjusted_text = adjust_text_by_hsk(option_text, hsk_num)
            pinyin_text = add_pinyin(adjusted_text) if type_config.get("show_pinyin", True) else adjusted_text

        option_label = type_config.get("options", ["A", "B", "C", "D", "E", "F", "G"])[idx]
        adjusted_options.append({
            "text": adjusted_text,
            "pinyin": pinyin_text,
            "label": option_label
        })

    # 显示问题
    st.markdown("### 请为下列问题选择最合适的回答：")
    for j, question in enumerate(adjusted_questions):
        question_format = type_config.get("question_format", "{index}. {question_text}")
        question_display = question_format.format(
            index=question.get("index", j + 1),
            question_text=question.get("pinyin", question.get("text", ""))
        )
        st.markdown(f"**{question_display}**")

        # 调试输出
        st.write(f"问题 {j + 1}: {question_display}")

        # 为每个问题创建独立的选择
        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = answers[j] if j < len(answers) else ""

        option_labels = [
            f"{opt['label']}. {opt['pinyin']}"
            for opt in adjusted_options
        ]

        # 调试输出
        st.write(f"选项: {option_labels}")

        selected_option = st.radio(
            f"请选择答案（问题 {j + 1}）:",
            option_labels,
            index=next(
                (idx for idx, opt in enumerate(option_labels)
                 if opt.startswith(f"{st.session_state[answer_key]}.")),
                0
            ),
            key=f"matching_{i}_{j}"
        )

        st.session_state[answer_key] = selected_option.split('.')[0].strip()


def handle_text_judgment2(q, level, category, i):
    """处理阅读判断题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    # 提取题目信息
    content = q.get("content", "")  # 阅读文本
    question = q.get("question", "")  # 需要判断的问题
    answer = q.get("answer", "")  # 正确答案
    explanation = q.get("explanation", "")  # 答案解析

    # 调整词汇并添加拼音
    adjusted_content = adjust_text_by_hsk(content, hsk_num)
    adjusted_question = adjust_text_by_hsk(question, hsk_num)

    if type_config.get("show_pinyin", False):
        content_with_pinyin = add_pinyin(adjusted_content)
        question_with_pinyin = add_pinyin(adjusted_question)
    else:
        content_with_pinyin = adjusted_content
        question_with_pinyin = adjusted_question

    # 显示阅读文本
    st.markdown("### 阅读文本：")
    st.markdown(content_with_pinyin)

    # 显示问题
    st.markdown("### 问题：")
    st.markdown(f"{type_config.get('question_format', '判断下列陈述是否正确：')}")
    st.markdown(f"**{question_with_pinyin}**")

    # 显示选项
    options = type_config.get("options", ["对", "错"])

    answer_key = f'answer_{i}'
    if answer_key not in st.session_state:
        st.session_state[answer_key] = answer if answer in options else options[0]

    selected_option = st.radio(
        "请选择：",
        options,
        index=options.index(st.session_state[answer_key]),
        key=f"judgment_{i}"
    )

    st.session_state[answer_key] = selected_option


def handle_sentence_matching2(q, level, category, i):
    """处理句子匹配题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))
    min_words = type_config.get("min_words")  # 获取最小字数

    # 提取题目信息
    sentences = q.get("sentences", [])  # 题干句子
    options = q.get("options", [])  # 选项句子
    answers = q.get("answers", [])  # 正确答案
    explanations = q.get("explanations", [])  # 答案解析

    # 调整词汇并添加拼音
    adjusted_sentences = []
    for idx, sentence in enumerate(sentences):
        if isinstance(sentence, str):
            sentence_text = sentence
            sentence_index = str(idx + 1)
        else:  # 字典格式
            sentence_text = sentence.get("text", "")
            sentence_index = sentence.get("index", str(idx + 1))

        adjusted_text = adjust_text_by_hsk(sentence_text, hsk_num)
        pinyin_text = add_pinyin(adjusted_text) if type_config.get("show_pinyin", True) else adjusted_text
        adjusted_sentences.append({
            "text": adjusted_text,
            "pinyin": pinyin_text,
            "index": sentence_index
        })

    adjusted_options = []
    for idx, option in enumerate(options):
        if isinstance(option, str):
            option_text = option
        else:  # 字典格式
            option_text = option.get("text", "")

        adjusted_text = adjust_text_by_hsk(option_text, hsk_num)
        pinyin_text = add_pinyin(adjusted_text) if type_config.get("show_pinyin", True) else adjusted_text
        option_label = chr(65 + idx)  # A, B, C, ...
        adjusted_options.append({
            "text": adjusted_text,
            "pinyin": pinyin_text,
            "label": option_label
        })

    # 显示题目说明
    st.markdown(f"### {type_config.get('question_format', '为下列句子选择最合适的答句：')}")

    # 为每个句子创建匹配选项
    for j, sentence in enumerate(adjusted_sentences):
        sentence_display = f"{sentence.get('index')}. {sentence.get('pinyin')}"
        st.markdown(f"**{sentence_display}**")

        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = answers[j] if j < len(answers) else ""

        option_labels = [
            f"{opt['label']}. {opt['pinyin']}"
            for opt in adjusted_options
        ]

        selected_option = st.radio(
            f"请选择匹配项（句子 {sentence.get('index')}）:",
            option_labels,
            index=next(
                (idx for idx, opt in enumerate(option_labels)
                 if opt.startswith(f"{st.session_state[answer_key]}.")),
                0
            ),
            key=f"matching_{i}_{j}"
        )

        st.session_state[answer_key] = selected_option.split('.')[0].strip()


def handle_reading_comprehension(q, level, category, i):
    """处理阅读理解题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    # 处理文章段落
    passages = q.get("passages", [])
    if isinstance(passages, str):
        st.warning("注意：passages字段应为列表，已将字符串转换为列表")
        passages = [passages]

    # 处理问题列表
    questions = q.get("questions", [])

    # 兼容旧格式（单个问题）
    if not questions and "question" in q:
        st.warning("注意：使用了旧格式的question字段，已转换为questions列表")
        question_text = q.get("question", "")
        options = q.get("options", [])
        if isinstance(options, dict):
            st.warning("注意：options字段应为列表，已将字典转换为列表")
            options = [v for k, v in sorted(options.items())]

        if question_text and options:
            questions = [{
                "text": question_text,
                "options": options,
                "answer": q.get("answer", "")
            }]
        else:
            st.error("无法从question字段构建有效问题，请检查数据")
            return

    # 验证问题列表
    if not isinstance(questions, list) or len(questions) == 0:
        st.error(f"题目数据错误：questions字段应为非空列表，当前值: {questions}")
        return

    # 显示文章
    st.markdown("### 阅读文章：")
    for passage in passages:
        adjusted_passage = adjust_text_by_hsk(passage, hsk_num)
        st.markdown(adjusted_passage)

    # 显示问题和选项
    st.markdown(f"### {type_config.get('question_format', '根据短文内容，回答问题：')}")

    # 处理每个问题
    for j, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            st.error(f"问题 {j} 格式错误：应为字典，当前值: {question}")
            return

        question_text = question.get("text", "")
        if not question_text.strip():
            st.error(f"问题 {j} 缺少text字段或text为空")
            return

        options = question.get("options", [])
        if not isinstance(options, list) or len(options) < 2:
            st.error(f"问题 {j} 的options字段应为至少包含两个选项的列表")
            return

        # 调整问题和选项的词汇
        adjusted_question_text = adjust_text_by_hsk(question_text, hsk_num)
        adjusted_options = [adjust_text_by_hsk(opt, hsk_num) for opt in options]

        # 显示问题
        st.markdown(f"**问题 {j}：** {adjusted_question_text}")

        # 选项格式
        option_format = type_config.get("options_format", "{label}. {option_text}")
        option_labels = [
            option_format.format(label=chr(65 + k), option_text=opt)
            for k, opt in enumerate(adjusted_options)
        ]

        # 存储用户答案的键
        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = ""

        # 获取正确答案
        correct_answer = question.get("answer", "")
        if correct_answer and isinstance(correct_answer, str) and correct_answer.isalpha():
            correct_answer = correct_answer.upper()
            # 找到正确答案在选项中的索引
            correct_index = next(
                (idx for idx, opt in enumerate(option_labels) if opt.startswith(f"{correct_answer}.")),
                0
            )
        else:
            correct_index = 0

        # 显示选项并获取用户选择
        selected_option = st.radio(
            f"请选择问题 {j} 的答案：",
            option_labels,
            index=next(
                (idx for idx, opt in enumerate(option_labels)
                 if opt.startswith(f"{st.session_state[answer_key]}.")),
                0
            ),
            key=f"reading_options_{i}_{j}"
        )

        # 保存用户选择
        st.session_state[answer_key] = selected_option.split('.')[0].strip()


def handle_image_matching(q, level, category, i):
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = get_hsk_level(level)

    sentences = q.get("sentences", [])
    options = q.get("options", [])
    answers = q.get("answers", [])

    st.markdown(f"### {type_config.get('question_format', '请将句子与对应的图片描述匹配')}")

    # 显示所有句子
    for j, sentence in enumerate(sentences):
        st.markdown(f"**句子 {j + 1}：** {sentence}")

    st.markdown("### 选项")
    cols = st.columns(len(options))
    for k, option in enumerate(options):
        img_bytes = generate_image_from_text(option)
        if img_bytes:
            cols[k].image(img_bytes, caption=f"选项 {chr(65 + k)}", use_container_width=True)

    # 让用户为每个句子选择匹配的图片描述
    for j in range(len(sentences)):
        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = ""

        selected_option = st.radio(
            f"请为句子 {j + 1} 选择匹配的图片描述：",
            [chr(65 + k) for k in range(len(options))],
            index=next(
                (idx for idx, opt in enumerate([chr(65 + k) for k in range(len(options))])
                 if opt == st.session_state[answer_key]),
                0
            ),
            key=f"matching_{i}_{j}"
        )

        st.session_state[answer_key] = selected_option

    with st.expander("查看答案与解析", expanded=False):
        for j, correct_answer in enumerate(answers):
            st.success(f"句子 {j + 1} 的正确答案：{correct_answer}")
            explanation = q.get("explanations", [""])[j]
            st.info(type_config.get('explanation_format', '').format(explanation=explanation))


def handle_connect_words_into_sentence(q, level, category, i):
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = get_hsk_level(level)

    words = q.get("words", [])  # 待连成句子的词语列表
    correct_answer = q.get("answer", "")  # 正确答案
    explanation = q.get("explanation", "")  # 答案解析

    st.markdown(f"### {type_config.get('question_format', '请将下列词语连成一个完整的句子：')}")

    # 显示词语，根据配置决定是否显示拼音
    word_display = []
    for word in words:
        if type_config.get("show_pinyin", False):
            word_display.append(add_pinyin(word))
        else:
            word_display.append(word)
    st.markdown(", ".join(word_display))

    # 让用户输入连成的句子
    answer_key = f'answer_{i}'

    # 初始化session_state值，如果不存在的话
    if answer_key not in st.session_state:
        st.session_state[answer_key] = ""

    # 获取当前值而不是直接赋值
    user_answer = st.text_input("请输入连成的句子", value=st.session_state[answer_key], key=answer_key)


def handle_audio_dialogue_questions(q, level, category, i):
    """处理听对话录音题（字典嵌套结构）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    # 提取听力材料和问题列表
    audio_content = q.get("audio_content", "")
    questions_data = q.get("questions", [])

    # 调试输出
    # st.write("调试：questions_data =", questions_data)

    if not questions_data:
        st.error("错误：缺少问题数据")
        return

    # 调整听力材料难度
    adjusted_dialogue = adjust_text_by_hsk(audio_content, hsk_num)

    # 播放对话录音
    st.markdown("🎧 **点击播放对话录音：**")
    dialogue_audio_file = f"temp_dialogue_{uuid.uuid4().hex}.mp3"

    try:
        asyncio.run(text_to_speech(adjusted_dialogue, dialogue_audio_file, level))
        play_audio_in_streamlit(dialogue_audio_file)

        if type_config.get("show_dialogue_text", False):
            st.markdown(f"**对话文本：** {adjusted_dialogue}")
    except Exception as e:
        st.error(f"生成或播放对话录音时出错: {str(e)}")
        return

    # 处理每个问题
    user_answers = {}

    for j, question_data in enumerate(questions_data):
        # 提取问题信息
        question_id = question_data.get("id", j + 1)
        question_text = question_data.get("text", f"问题{question_id}")
        options = question_data.get("options", [])
        answer = question_data.get("answer", "")
        explanation = question_data.get("explanation", "")

        # 调试输出
        # st.write(f"调试：处理问题 {question_id}: {question_text}")
        # st.write(f"调试：选项 = {options}")

        if not options:
            st.warning(f"警告：问题 {question_id} 缺少选项")
            continue

        # 生成问题音频（根据配置或问题单独设置）
        question_audio_file = f"temp_question_{question_id}_{uuid.uuid4().hex}.mp3"
        question_audio_enabled = question_data.get("audio_enabled", type_config.get("question_audio_enabled", True))

        # 问题容器
        with st.container():
            col1, col2 = st.columns([9, 1])

            with col1:
                st.markdown(f"### **问题 {question_id}：")

            with col2:
                if question_audio_enabled:
                    try:
                        # 优先使用预先生成的音频路径
                        audio_path = question_data.get("audio_path")
                        if audio_path and os.path.exists(audio_path):
                            st.audio(audio_path, format="audio/mp3", start_time=0)
                        else:
                            asyncio.run(text_to_speech(question_text, question_audio_file, level))
                            st.audio(question_audio_file, format="audio/mp3", start_time=0)
                    except Exception as e:
                        st.error(f"生成或播放问题 {question_id} 音频时出错: {str(e)}")

            # 生成选项标签
            option_labels = [f"{opt}" for opt in options]  # 选项已包含ABCD，无需重新生成

            # 创建单选框
            answer_key = f"dialogue_answer_{i}_{question_id}"
            selected_option = st.radio(
                label=f"请选择问题 {question_id} 的答案：",
                options=option_labels,
                key=answer_key
            )

            # 保存用户答案
            user_answer = selected_option.split('.')[0].strip() if selected_option else ""
            user_answers[question_id] = (user_answer, answer, explanation)

    # 提交按钮和结果验证
    if st.button("提交答案", key=f"submit_dialogue_{i}"):
        correct_count = 0

        for question_id, (user_answer, correct_answer, explanation) in user_answers.items():
            if user_answer == correct_answer:
                correct_count += 1
                result_icon = "✅"
            else:
                result_icon = "❌"

            # 显示结果和解释
            with st.expander(f"问题 {question_id} 结果"):
                st.markdown(f"**你的答案：** {user_answer}")
                st.markdown(f"**正确答案：** {correct_answer} {result_icon}")

                if explanation:
                    st.markdown(f"**解析：** {explanation}")

        # 显示总得分
        score = f"{correct_count}/{len(questions_data)}"
        st.success(f"得分：{score} ({correct_count / len(questions_data):.0%})")

        # 清理临时文件
        if os.path.exists(dialogue_audio_file):
            os.remove(dialogue_audio_file)


def handle_sentence_sorting(q, level, category, i):
    """句子排序题处理器"""
    config = DETAILED_QUESTION_CONFIG[level][category]["句子排序题"]
    sentences = q.get("sentences", [])  # 原始句子列表（乱序）
    correct_order = q.get("answer", [])  # 正确顺序（如 ["C", "B", "A"]）
    hsk_num = q.get("vocab_level", config.get("vocab_level", 4))

    # 提取标签和内容
    labels = [sentence.split('.')[0] for sentence in sentences]
    contents = [sentence.split('.', 1)[1].strip() for sentence in sentences]

    st.subheader(f"句子排序题 #{i + 1}")
    st.markdown(f"**题目：** {config['question_content']}", hsk_num)
    st.markdown(f"**提示：** {config['sort_hint']}")

    # 显示原始句子
    st.markdown("### 请将下列句子按正确顺序排列：")
    for idx, content in enumerate(contents):
        st.markdown(f"{labels[idx]}. {content}")

    # 创建排序选择器
    available_labels = labels.copy()
    user_order = []

    for position in range(len(labels)):
        selected_label = st.selectbox(
            f"第 {position + 1} 句的正确标签是：",
            available_labels,
            key=f"sort_{i}_{position}"
        )
        user_order.append(selected_label)
        available_labels.remove(selected_label)

    if st.button("提交答案", key=f"submit_{i}"):
        if user_order == correct_order:
            st.success("回答正确！")
        else:
            st.error("回答错误，请重新尝试。")

        # 显示解析
        explanation = q.get("explanation", "请根据逻辑关系排序。")
        st.markdown(config["explanation_format"].format(
            correct_order=" → ".join(correct_order),
            explanation=explanation
        ))


def handle_passage_filling5(q, level, category, i):
    """短文选词填空题处理器"""
    config = DETAILED_QUESTION_CONFIG[level][category]["短文选词填空题5"]
    passages = q.get("passages")
    gaps = q.get("gaps", [])  # 空位信息（包含选项和答案）
    hsk_num = q.get("vocab_level", config.get("vocab_level", 5))

    st.write("调试：短文选词填空题数据结构 =", q)

    # 1. 先尝试读取passages字段（优先）
    passages = q.get("passages", [])

    # 处理passages为列表的情况
    if isinstance(passages, list):
        passage_text = "\n\n".join(passages).strip()
    else:
        passage_text = str(passages).strip()

    # 2. 如果passages内容长度不足20，读取content字段
    if len(passage_text) < 20:
        st.write(f"调试：passages长度为{len(passage_text)}，切换至读取content字段")
        passage_text = q.get("content", "").strip()

    # 3. 验证最终内容是否存在
    if not passage_text:
        st.error("错误：短文内容（passages或content）为空")
        return

    # 显示短文
    st.markdown("### 阅读短文：")
    adjusted_passage = adjust_text_by_hsk(passage_text, hsk_num)
    st.markdown(adjusted_passage)

    # 处理每个空位
    st.markdown("### 请选择合适的词填入空格：")
    user_answers = []
    for gap_idx, gap in enumerate(gaps, 1):
        gap_text = config["gap_format"].format(gap_number=gap_idx)
        options = gap.get("options", [])
        answer = gap.get("answer", "A")

        # 调整选项词汇等级
        adjusted_options = [adjust_text_by_hsk(opt, hsk_num) for opt in options]

        # 显示空位和选项
        st.markdown(f"**第 {gap_idx} 题** {gap_text}")
        selected = st.radio(
            "选项：",
            [f"{chr(65 + k)}. {opt}" for k, opt in enumerate(adjusted_options)],
            key=f"gap_{i}_{gap_idx}"
        )
        user_answers.append(selected.split(". ")[0])

    # 提交答案和验证
    if st.button(f"提交答案", key=f"submit_{i}"):
        correct = True
        for gap_idx, (user_ans, gap) in enumerate(zip(user_answers, gaps), 1):
            correct_ans = gap.get("answer", "A").upper()
            if user_ans != correct_ans:
                correct = False
                break

        if correct:
            st.success("所有空位回答正确！")
        else:
            st.error("回答错误，请检查空位答案。")

        # 显示解析（示例）
        for gap_idx, gap in enumerate(gaps, 1):
            st.markdown(f"**第 {gap_idx} 题解析：**")
            st.markdown(config["explanation_format"].format(
                answer=gap.get("answer", "A"),
                explanation=gap.get("explanation", "根据上下文逻辑选择")
            ))


def handle_passage_filling6(q, level, category, i):
    """短文选词填空题处理器"""
    # 获取配置信息
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {})
    min_gaps = config.get("min_gaps", 1)
    gap_format = config.get("gap_format", "______")
    show_explanation = config.get("show_explanation", True)
    hsk_num = q.get("vocab_level", config.get("vocab_level", 6))

    st.write("调试：短文选词填空题数据结构 =", q)

    # ------------------------------
    # 1. 解析短文内容
    # ------------------------------
    passages = q.get("passages", [])
    if isinstance(passages, list):
        passage_text = "\n\n".join(passages).strip()  # 合并多段落
    else:
        passage_text = str(passages).strip()

    # 兼容content字段（可选）
    if not passage_text:
        passage_text = q.get("content", "").strip()

    if not passage_text:
        st.error("错误：短文内容为空")
        return

    # ------------------------------
    # 2. 解析空位和选项
    # ------------------------------
    gaps = q.get("gaps", [])

    # 验证空位数量
    if len(gaps) < min_gaps:
        st.error(f"错误：至少需要{min_gaps}个空位，当前{len(gaps)}个")
        return

    # 确保每个空位包含必要字段
    for gap in gaps:
        if not gap.get("options") or not gap.get("answer"):
            st.error("错误：空位信息不完整（需包含options和answer）")
            return

    # ------------------------------
    # 3. 显示短文和空位
    # ------------------------------
    st.markdown("### 短文阅读：")
    adjusted_passage = adjust_text_by_hsk(passage_text, hsk_num)  # 假设存在词汇调整函数
    st.markdown(adjusted_passage)

    st.markdown("### 请选择合适的词填入空格：")
    user_answers = []

    for gap in gaps:
        gap_number = gap["gap_number"]
        options = gap["options"]
        correct_answer = gap["answer"].upper()
        explanation = gap.get("explanation", "根据上下文逻辑选择")

        # 格式化选项（确保以A/B/C/D开头）
        formatted_options = []
        for idx, opt in enumerate(options):
            if not opt.startswith(("A.", "B.", "C.", "D.")):
                formatted_options.append(f"{chr(65 + idx)}. {opt}")
            else:
                formatted_options.append(opt)

        # 显示空位和选项
        st.markdown(f"**第 {gap_number} 题**：{gap_format}")
        selected = st.radio(
            "选项：",
            formatted_options,
            key=f"gap_{i}_{gap_number}"
        )
        user_answers.append({
            "gap_number": gap_number,
            "user_answer": selected.split(". ")[0],  # 提取选项字母
            "correct_answer": correct_answer,
            "explanation": explanation
        })

    # ------------------------------
    # 4. 提交答案和验证
    # ------------------------------
    if st.button(f"提交答案", key=f"submit_passage_{i}"):
        correct_count = 0
        results = []

        for ans in user_answers:
            user_ans = ans["user_answer"].upper()
            # 确保correct_answer存在
            correct_ans = ans.get("correct_answer", "")  # 使用get方法避免KeyError
            is_correct = user_ans == correct_ans
            results.append({
                "gap_number": ans["gap_number"],
                "is_correct": is_correct,
                "correct_answer": correct_ans,  # 明确包含correct_answer
                "explanation": ans["explanation"]
            })
            if is_correct:
                correct_count += 1

        # 显示结果汇总
        total = len(user_answers)
        st.info(f"共回答 {total} 题，正确 {correct_count} 题，正确率 {correct_count / total:.0%}")

        # 显示详细解析
        if show_explanation:
            st.markdown("### 答案解析：")
            for res in results:
                status = "✅ 正确" if res["is_correct"] else "❌ 错误"
                st.markdown(f"**第 {res['gap_number']} 题**：{status}")
                st.markdown(f"**正确答案**：{res['correct_answer']}")
                st.markdown(f"**解析**：{res['explanation']}")
                st.markdown("---")


def handle_reading_multiple_choice(q, level, category, i):
    """阅读文章选择题处理器（完全避免渲染后修改session_state）"""
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get("阅读文章选择题", {})
    hsk_num = q.get("vocab_level", config.get("vocab_level", 4))

    st.write("调试：阅读选择题数据结构 =", q)

    # 1. 获取文章内容
    passage = ""
    if "passages" in q:
        if isinstance(q["passages"], list) and q["passages"]:
            passage = q["passages"][0]
        elif isinstance(q["passages"], str):
            passage = q["passages"]

    if not passage and "content" in q:
        passage = q["content"]

    # 2. 统一问题格式
    questions = []
    if "questions" in q and isinstance(q["questions"], list):
        questions = q["questions"]
    else:
        if "question" in q or "options" in q:
            questions.append({
                "text": q.get("question", ""),
                "options": q.get("options", []),
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", "")
            })

    # 验证数据
    if not passage.strip():
        st.error("错误：文章内容为空")
        return

    if not questions:
        st.error("错误：未找到有效问题")
        st.json(q)
        return

    # 显示处理后的数据结构
    st.write("处理后的数据结构:", {
        "passage": passage[:50] + "..." if len(passage) > 50 else passage,
        "question_count": len(questions)
    })

    # 预初始化所有session_state键
    for j in range(1, len(questions) + 1):
        answer_key = f"reading_{i}_{j}"
        if answer_key not in st.session_state:
            st.session_state[answer_key] = None

    # 提交答案回调函数
    def submit_answers():
        st.session_state.submitted = True

    # 重置答案回调函数
    def reset_answers():
        for j in range(1, len(questions) + 1):
            answer_key = f"reading_{i}_{j}"
            st.session_state[answer_key] = None
        if 'submitted' in st.session_state:
            del st.session_state.submitted

    # 显示文章
    st.markdown("### 阅读文章：")
    adjusted_passage = adjust_text_by_hsk(passage, hsk_num)
    st.markdown(adjusted_passage)

    # 处理每个问题
    st.markdown(f"### 请根据文章内容回答问题（共{len(questions)}题）：")
    for j, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            continue

        q_text = question.get("text", f"问题{j}")
        options = question.get("options", [])
        answer = str(question.get("answer", "")).upper()
        explanation = question.get("explanation", "")

        # 调整词汇等级
        adjusted_q = adjust_text_by_hsk(q_text, hsk_num)
        adjusted_options = [adjust_text_by_hsk(opt, hsk_num) for opt in options]

        # 格式化选项标签
        option_labels = []
        for k, opt in enumerate(adjusted_options):
            opt = re.sub(r'^[A-Da-d]\.?\s*', '', opt).strip()
            option_labels.append(f"{chr(65 + k)}. {opt}")

        # 创建单选框
        answer_key = f"reading_{i}_{j}"
        default_index = 0

        if st.session_state[answer_key] is not None:
            saved_answer = st.session_state[answer_key]
            default_index = next(
                (idx for idx, opt in enumerate(option_labels) if opt == saved_answer),
                0
            )

        # 只读取session_state，不修改
        st.radio(
            f"问题 {j}：{adjusted_q}",
            option_labels,
            index=default_index,
            key=answer_key
        )

    # 按钮区域
    col1, col2 = st.columns(2)
    with col1:
        st.button("提交答案", on_click=submit_answers)
    with col2:
        st.button("重置答案", on_click=reset_answers)

    # 显示结果（仅在提交后）
    if 'submitted' in st.session_state and st.session_state.submitted:
        # 计算得分
        correct_count = 0
        total_questions = len(questions)

        st.markdown(f"### ✅ **答题结果：**")

        # 显示每个问题的结果
        for j in range(1, total_questions + 1):
            answer_key = f"reading_{i}_{j}"
            if answer_key not in st.session_state or st.session_state[answer_key] is None:
                st.warning(f"问题 {j}：未作答")
                continue

            user_choice = st.session_state[answer_key].split('.')[0].strip()
            correct_answer = questions[j - 1].get("answer", "").upper()
            explanation = questions[j - 1].get("explanation", "")
            is_correct = user_choice == correct_answer

            if is_correct:
                correct_count += 1

            status = "✅ 正确" if is_correct else "❌ 错误"

            st.markdown(f"#### **问题 {j}：** {questions[j - 1].get('text', '')}")
            st.markdown(f"**你的答案：** {user_choice} → {status}")
            st.markdown(f"**正确答案：** {correct_answer}")

            if not is_correct and explanation:
                st.info(f"**解析：** {explanation}")
            st.markdown("---")

        # 更新得分
        st.markdown(f"### ✅ **最终得分：**")
        st.markdown(f"**答对：{correct_count}/{total_questions}题**")


def handle_long_text_comprehension(q, level, category, i):
    """处理长文本理解题（修复嵌套列表格式的选项）"""
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get("长文本理解题", {})
    hsk_num = q.get("vocab_level", config.get("vocab_level", 4))

    st.write("调试：长文本理解题数据结构 =", q)

    # 获取长文本内容（不变）
    text = q.get("text", "")
    if not text.strip():
        text = q.get("passage", "")
        text = q.get("content", text)

    if not text.strip():
        st.error("错误：长文本内容为空")
        return

    # 获取问题列表（增强兼容旧格式）
    questions = q.get("questions", [])

    # 兼容旧格式：question字段为列表（包含问题文本和选项）
    if not questions and "question" in q and isinstance(q["question"], list):
        st.warning("注意：检测到question字段为列表，已自动转换为字典格式")
        question_list = q["question"]
        if len(question_list) > 0:
            question_text = question_list[0]  # 列表第一个元素为问题文本
            # 尝试从options字段或question列表后续元素获取选项
            options = []
            if "options" in q and isinstance(q["options"], list):
                # 处理嵌套列表格式的options
                if q["options"] and isinstance(q["options"][0], list):
                    options = q["options"][0]  # 提取第一层嵌套列表
                else:
                    options = q["options"]
            elif len(question_list) > 1:
                options = question_list[1:]  # 使用question列表后续元素作为选项

            questions = [{
                "text": question_text,
                "options": options,
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", "")
            }]
        else:
            st.error("错误：question字段为空列表")
            return

    # 兼容旧格式：question字段为字符串
    if not questions and "question" in q and isinstance(q["question"], str):
        st.warning("注意：使用了旧格式的question字段，已转换为questions列表")
        options = q.get("options", [])
        # 处理嵌套列表格式的options
        if options and isinstance(options[0], list):
            options = options[0]  # 提取第一层嵌套列表

        questions = [{
            "text": q["question"],
            "options": options,
            "answer": q.get("answer", ""),
            "explanation": q.get("explanation", "")
        }]

    # 验证问题数量（不变）
    if not questions:
        st.error("错误：未找到问题")
        return

    if len(questions) < config.get("min_questions", 1):
        st.error(f"错误：至少需要{config.get('min_questions', 1)}个问题")
        return

    # 显示长文本（不变）
    st.markdown("### 阅读材料：")
    adjusted_text = adjust_text_by_hsk(text, hsk_num)
    paragraphs = adjusted_text.split('\n\n')
    for para in paragraphs:
        if para.strip():
            st.markdown(para)
            st.markdown("")

    # 显示问题（不变）
    st.markdown(f"### {config.get('question_format', '根据文章内容，回答问题：')}")

    # 处理每个问题
    for j, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            st.error(f"问题 {j} 格式错误：应为字典，实际为{type(question)}")
            continue

        # 获取问题文本（不变）
        question_text = question.get("text", f"问题 {j}")
        if isinstance(question_text, list):
            question_text = " ".join(question_text).strip()

        if not question_text.strip():
            st.error(f"问题 {j} 的文本为空")
            question_text = f"问题 {j}（文本缺失）"

        # 获取选项（增强处理嵌套列表）
        options = question.get("options", [])

        # 处理嵌套列表格式的options
        if options and isinstance(options[0], list):
            st.warning(f"问题 {j} 的options是嵌套列表，已自动展平")
            options = options[0]  # 提取第一层嵌套列表

        if not options:
            st.error(f"问题 {j} 的选项为空")
            options = ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"]

        # 格式化选项（不变）
        formatted_options = []
        for k, opt in enumerate(options):
            if isinstance(opt, str):
                if not opt.strip().startswith(("A.", "B.", "C.", "D.")):
                    prefix = chr(65 + k) + "."
                    formatted_options.append(f"{prefix} {opt}")
                else:
                    formatted_options.append(opt)
            else:
                formatted_options.append(f"{chr(65 + k)}. {str(opt)}")

        # 创建单选组件（不变）
        answer_key = f"long_text_answer_{i}_{j}"
        selected_option = st.radio(
            f"问题 {j}: {question_text}",
            formatted_options,
            key=answer_key
        )

    # 提交按钮及结果验证（不变）
    if st.button(f"提交答案", key=f"submit_long_text_{i}"):
        correct_count = 0
        total_count = len(questions)

        for j, question in enumerate(questions, 1):
            answer_key = f"long_text_answer_{i}_{j}"
            user_answer = st.session_state.get(answer_key, "").split('.')[0].strip()
            correct_answer = question.get("answer", "").upper()

            if user_answer == correct_answer:
                correct_count += 1

        st.info(f"共回答 {total_count} 题，正确 {correct_count} 题，正确率 {correct_count / total_count:.0%}")

        if config.get("show_explanation", True):
            st.markdown("### 答案解析：")
            for j, question in enumerate(questions, 1):
                answer_key = f"long_text_answer_{i}_{j}"
                user_answer = st.session_state.get(answer_key, "").split('.')[0].strip()
                correct_answer = question.get("answer", "").upper()
                explanation = question.get("explanation", "根据文章内容选择最佳答案")

                status = "✅ 正确" if user_answer == correct_answer else "❌ 错误"

                st.markdown(f"**问题 {j}：** {question.get('text', '')}")
                st.markdown(f"**你的答案：** {user_answer} → {status}")
                st.markdown(f"**正确答案：** {correct_answer}")
                st.markdown(f"**解析：** {explanation}")
                st.markdown("---")


def handle_sentence_filling(q, level, category, i):
    """短文选句填空题处理器"""
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {})
    min_gaps = config.get("min_gaps", 5)
    gap_format = config.get("gap_format", "__{gap_number}__")
    show_explanation = config.get("show_explanation", True)
    hsk_num = q.get("vocab_level", config.get("vocab_level", 6))

    st.write("调试：短文选句填空题数据结构 =", q)

    # 解析短文和空位逻辑（与选词填空类似）
    passage_text = q.get("passages", [""])[0].strip()
    gaps = q.get("gaps", [])

    if not passage_text or len(gaps) < min_gaps:
        st.error("错误：短文内容或空位数不足")
        return

    # 显示短文
    st.markdown("### 短文阅读：")
    adjusted_passage = adjust_text_by_hsk(passage_text, hsk_num)
    st.markdown(adjusted_passage)

    # 处理每个空位
    st.markdown("### 请选择合适的句子填入空格：")
    user_answers = []

    for gap in gaps:
        gap_number = gap["gap_number"]
        options = gap["options"]
        correct_answer = gap["answer"].upper()
        explanation = gap.get("explanation", "根据上下文逻辑选择")

        # 格式化选项（确保以A/B/C/D/E开头）
        formatted_options = [f"{opt}" for opt in options]  # 直接使用选项文本（已包含字母前缀）

        # 显示空位和选项
        st.markdown(f"**第 {gap_number} 题**：{gap_format.format(gap_number=gap_number)}")
        selected = st.radio(
            "选项：",
            formatted_options,
            key=f"sentence_gap_{i}_{gap_number}"
        )
        user_answers.append({
            "gap_number": gap_number,
            "user_answer": selected[0],  # 提取选项字母（A/B/C/D/E）
            "correct_answer": correct_answer,
            "explanation": explanation
        })

    # 提交答案和验证逻辑（与选词填空一致）
    if st.button(f"提交答案", key=f"submit_sentence_{i}"):
        correct_count = 0
        results = []
        for ans in user_answers:
            user_ans = ans["user_answer"].upper()
            is_correct = user_ans == ans["correct_answer"]
            results.append({
                "gap_number": ans["gap_number"],
                "is_correct": is_correct,
                "correct_answer": ans["correct_answer"],
                "explanation": ans["explanation"]
            })
            if is_correct:
                correct_count += 1

        st.info(f"共回答 {len(results)} 题，正确 {correct_count} 题，正确率 {correct_count / len(results):.0%}")

        if show_explanation:
            st.markdown("### 答案解析：")
            for res in results:
                st.markdown(f"**第 {res['gap_number']} 题**：{'✅ 正确' if res['is_correct'] else '❌ 错误'}")
                st.markdown(f"**正确答案**：{res['correct_answer']}. {options[ord(res['correct_answer']) - 65]}")  # 显示完整选项
                st.markdown(f"**解析**：{res['explanation']}")
                st.markdown("---")


def handle_sentence_error_choice(q, level, category, i):
    """处理病句选择题"""
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get("病句选择题", {})
    hsk_num = q.get("vocab_level", config.get("vocab_level", 4))

    # 获取题目信息
    question_text = q.get("question", "请选出有语病的一项")
    options = q.get("options", [])
    correct_answer = q.get("answer", "")
    explanation = q.get("explanation", "")
    error_type = q.get("error_type", "未知")  # 可选：记录语病类型

    # 验证选项数量
    if len(options) != config.get("max_sentences", 4):
        st.warning(f"警告：题目应有4个选项，当前有{len(options)}个，将自动填充空选项")
        while len(options) < 4:
            options.append("")

    # 显示题目
    st.markdown(f"### {question_text}")

    # 显示选项
    formatted_options = []
    for idx, sentence in enumerate(options, 1):
        label = chr(65 + idx - 1)  # A/B/C/D
        formatted_options.append(f"{label}. {sentence}")

    # 创建单选组件
    answer_key = f"error_choice_{i}"
    selected_option = st.radio(
        "请选择答案：",
        formatted_options,
        key=answer_key
    )

    # 提交按钮
    if st.button(f"提交第 {i + 1} 题答案", key=f"submit_error_{i}"):
        user_answer = selected_option.split('.')[0].strip()
        correct = user_answer == correct_answer

        # 显示结果
        if correct:
            st.success("回答正确！")
        else:
            st.error(f"回答错误，正确答案为：{correct_answer}")

        # 显示解析
        if config.get("show_explanation", True) and explanation:
            st.markdown("### 解析：")
            st.markdown(f"**语病类型**：{error_type}")
            st.markdown(f"**错误选项**：{user_answer} —— {selected_option.split('.', 1)[1].strip()}")
            st.markdown(f"**正确解析**：{explanation}")


def handle_reading_1v2(q, level, category, i):
    """处理1篇文章+多道题的阅读理解题（增强版）"""
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", config.get("vocab_level", 4))

    st.write("调试：阅读选择题数据结构 =", q)

    # 解析文章内容
    passages = q.get("passages", [])
    if not passages or len(passages) != 1:
        st.error("错误：需包含且仅包含1篇文章")
        return

    passage = passages[0].strip()
    adjusted_passage = adjust_text_by_hsk(passage, hsk_num)

    # 解析问题列表（兼容多种格式）
    questions_data = []

    # 标准格式：questions字段为字典列表
    if "questions" in q and isinstance(q["questions"], list):
        questions_data = q["questions"]

    # 旧格式：question字段为字符串列表，选项全局共享
    elif "question" in q and isinstance(q["question"], list):
        question_texts = q["question"]
        all_options = q.get("options", [])
        answers = q.get("answer", "").split(",") if isinstance(q.get("answer"), str) else q.get("answer", [])

        # 为每个问题分配独立的选项组
        options_per_question = 4  # 每个问题4个选项
        total_questions = len(question_texts)

        # 验证选项总数是否足够
        if len(all_options) < total_questions * options_per_question:
            st.warning(f"警告：选项数量不足，应为每个问题提供{options_per_question}个选项")

        for j, text in enumerate(question_texts):
            # 计算当前问题的选项范围
            start_idx = j * options_per_question
            end_idx = start_idx + options_per_question

            # 从全局选项中提取当前问题的选项
            question_options = all_options[start_idx:end_idx]

            # 如果选项不足，用占位符填充
            while len(question_options) < options_per_question:
                question_options.append(f"选项{chr(65 + len(question_options))}（数据缺失）")

            # 获取对应答案（如果存在）
            answer = answers[j] if j < len(answers) else ""

            questions_data.append({
                "text": text,
                "options": question_options,
                "answer": answer,
                "explanation": q.get("explanation", "")
            })

    # 单问题扁平化格式
    elif "question" in q:
        questions_data = [{
            "text": q.get("question", ""),
            "options": q.get("options", []),
            "answer": q.get("answer", ""),
            "explanation": q.get("explanation", "")
        }]

    if not questions_data:
        st.error("错误：缺少问题数据")
        return

    # 调试：显示解析后的问题数量
    st.write(f"调试：解析出 {len(questions_data)} 个问题")

    # 显示文章
    st.markdown("### 阅读文章：")
    st.markdown(adjusted_passage)

    # 处理每个问题
    user_answers = {}
    for j, question_data in enumerate(questions_data, 1):
        question_id = question_data.get("id", j)
        question_text = question_data.get("text", f"问题{j}")
        options = question_data.get("options", [])
        answer = question_data.get("answer", "").upper()
        explanation = question_data.get("explanation", "")

        if not options:
            st.warning(f"警告：问题{question_id}缺少选项")
            continue

        st.markdown(f"### **问题 {question_id}：** {question_text}")

        # 创建单选组件（确保选项格式正确）
        option_labels = []
        for k, opt in enumerate(options):
            # 处理选项格式（如果已经包含A. B.前缀，则不重复添加）
            if opt.startswith(("A.", "B.", "C.", "D.", "E.", "F.", "G.", "H.")):
                option_labels.append(opt)
            else:
                option_labels.append(f"{chr(65 + k)}. {opt}")

        selected_option = st.radio(
            "请选择答案：",
            option_labels,
            key=f"reading_{i}_{question_id}"
        )

        # 提取用户选择的字母
        user_answer = selected_option.split(".")[0].strip() if selected_option else ""
        user_answers[question_id] = (user_answer, answer, explanation)

    # 提交按钮及结果统计
    material_id = q.get("id", uuid.uuid4().hex)
    if st.button("提交阅读答案", key=f"submit_reading_{material_id}_{i}"):
        correct_count = 0
        for question_id, (user_answer, correct_answer, explanation) in user_answers.items():
            with st.expander(f"问题 {question_id} 结果"):
                st.markdown(f"**你的答案：** {user_answer}")
                st.markdown(f"**正确答案：** {correct_answer} {'✅' if user_answer == correct_answer else '❌'}")
                if explanation:
                    st.markdown(f"**解析：** {explanation}")
            if user_answer == correct_answer:
                correct_count += 1

        score = f"{correct_count}/{len(questions_data)}"
        st.success(f"得分：{score} ({correct_count / len(questions_data):.0%})")


def handle_article_questions(q, level, category, i):
    """文章选择题处理器"""
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {})
    min_questions = config.get("min_questions", 4)
    question_format = config.get("question_format", "根据文章内容，回答问题：")
    show_explanation = config.get("show_explanation", True)
    hsk_num = q.get("vocab_level", config.get("vocab_level", 6))

    st.write("调试：文章选择题数据结构 =", q)

    # ------------------------------
    # 1. 解析文章内容
    # ------------------------------
    passages = q.get("passages", [])
    article_text = "\n\n".join(passages).strip()  # 合并多段落

    if not article_text:
        st.error("错误：文章内容为空")
        return

    # ------------------------------
    # 2. 解析问题列表
    # ------------------------------
    questions = q.get("questions", [])

    # 验证题目数量
    if len(questions) < min_questions:
        st.error(f"错误：至少需要{min_questions}个问题，当前{len(questions)}个")
        return

    # ------------------------------
    # 3. 显示文章和问题
    # ------------------------------
    st.markdown("### 阅读文章：")
    adjusted_text = adjust_text_by_hsk(article_text, hsk_num)  # 调整文本难度
    st.markdown(adjusted_text)

    st.markdown(f"### {question_format}")

    user_answers = []
    for question in questions:
        q_id = question["question_id"]
        q_text = question["text"]
        options = question["options"]
        correct_answer = question["answer"].upper()
        explanation_key = question.get("explanation_key", "")

        # 显示问题和选项
        st.markdown(f"**问题 {q_id}：** {q_text}")
        selected = st.radio(
            "选项：",
            options,
            key=f"article_q_{i}_{q_id}"
        )
        user_answers.append({
            "question_id": q_id,
            "user_answer": selected[0],  # 提取选项字母（A/B/C/D）
            "correct_answer": correct_answer,
            "explanation_key": explanation_key
        })

    # ------------------------------
    # 4. 提交答案和验证
    # ------------------------------
    if st.button(f"提交答案", key=f"submit_article_{i}"):
        correct_count = 0
        results = []

        for ans in user_answers:
            user_ans = ans["user_answer"].upper()
            is_correct = user_ans == ans["correct_answer"]
            results.append({
                "question_id": ans["question_id"],
                "is_correct": is_correct,
                "correct_answer": ans["correct_answer"],
                "explanation_key": ans["explanation_key"]
            })
            if is_correct:
                correct_count += 1

        # 显示结果汇总
        total = len(user_answers)
        st.info(f"共回答 {total} 题，正确 {correct_count} 题，正确率 {correct_count / total:.0%}")

        # 显示详细解析
        if show_explanation:
            st.markdown("### 答案解析：")
            for res in results:
                # 确保 config 包含 explanation_format ✅
                explanation = config.get("explanation_format", "解析：{answer} 是正确答案。").format(
                    question_id=res["question_id"],
                    answer=res["correct_answer"],
                    explanation_key=res["explanation_key"]
                )
                st.markdown(f"**问题 {res['question_id']}**：{'✅ 正确' if res['is_correct'] else '❌ 错误'}")
                st.markdown(f"**解析**：{explanation}")
                st.markdown("---")


def handle_article_listening(q, level, category, i):
    """处理听短文选择题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 6))

    st.write("调试：文章选择题数据结构 =", q)

    # 提取题目信息
    article_content = q.get("audio_content", "")
    questions = q.get("questions", [])

    # 调整词汇难度
    adjusted_article = adjust_text_by_hsk(article_content, hsk_num)
    adjusted_questions = [
        {
            "question": adjust_text_by_hsk(q["question"], hsk_num),
            "options": [adjust_text_by_hsk(option, hsk_num) for option in q["options"]],
            "answer": q["answer"],
            "explanation": q.get("explanation", "")
        }
        for q in questions
    ]

    # 生成文章音频
    st.markdown("🎧 **请听文章：**")
    article_audio = f"temp_article_{uuid.uuid4().hex}.mp3"

    try:
        # 异步生成文章音频（使用男声）
        asyncio.run(text_to_speech(adjusted_article, article_audio, level, role='male'))
        play_audio_in_streamlit(article_audio)

        # 可选：显示文章文本
        if type_config.get("show_audio_text", False):
            with st.expander("查看文章原文"):
                st.markdown(adjusted_article)

    except Exception as e:
        st.error(f"生成文章音频时出错: {str(e)}")
    finally:
        st.session_state.temp_files.append(article_audio)

    # 显示问题和选项
    st.markdown("### ❓ **问题与选项：**")

    user_answers = {}
    for j, question_data in enumerate(adjusted_questions):
        question_key = f'article_{i}_q{j}'
        question_text = question_data["question"]
        options = question_data["options"]

        # 保存用户答案
        if question_key not in st.session_state:
            st.session_state[question_key] = None

        st.markdown(f"#### **问题{j + 1}：** {question_text}")

        # 创建选项单选框
        selected_option = st.radio(
            f"请选择问题{j + 1}的答案：",
            options,
            index=options.index(st.session_state[question_key])
            if st.session_state[question_key] in options else 0,
            key=f"article_{i}_options_{j}"
        )

        st.session_state[question_key] = selected_option
        user_answers[j] = selected_option

    # 提交答案按钮
    if st.button("提交答案"):
        correct_count = 0
        results = []

        for j, question_data in enumerate(questions):
            user_choice = user_answers[j].split('.')[0].strip()
            correct_answer = question_data["answer"]
            is_correct = user_choice == correct_answer

            if is_correct:
                correct_count += 1

            results.append({
                "question_num": j + 1,
                "is_correct": is_correct,
                "user_answer": user_choice,
                "correct_answer": correct_answer,
                "explanation": question_data.get("explanation", "")
            })

        # 显示结果
        st.markdown(f"### ✅ **答题结果：**")
        st.markdown(f"**答对：{correct_count}题 / 共{len(questions)}题**")

        for result in results:
            status = "✅ 正确" if result["is_correct"] else "❌ 错误"
            st.markdown(f"**问题{result['question_num']}：** {status}")
            st.markdown(f"- 你的答案：{result['user_answer']}")
            st.markdown(f"- 正确答案：{result['correct_answer']}")

            if not result["is_correct"] and result["explanation"]:
                st.info(f"**解析：** {result['explanation']}")


# 题型处理器映射
QUESTION_HANDLERS = {
    "听力看图判断题": handle_look_and_judge1,
    "阅读看图判断题": handle_look_and_judge2,
    "看图选择题": handle_look_and_choice,
    "图片排序题": handle_image_sorting,
    "听录音选择题": handle_listening,
    "选词填空题": handle_fill_in_the_blank,
    "图片匹配题": handle_image_matching,
    "文字判断题": handle_text_judgment1,
    "问答匹配题": handle_sentence_matching1,
    "阅读判断题": handle_text_judgment2,
    "句子匹配题": handle_sentence_matching2,
    "阅读理解题": handle_reading_comprehension,
    "听对话选择题": handle_listening,
    "听对话选择题4": handle_listening,
    "听对话选择题5": handle_listening,
    "听对话选择题6": handle_listening,
    "连词成句": handle_connect_words_into_sentence,
    "听对话选择题1v2": handle_audio_dialogue_questions,
    "听对话选择题1v3": handle_audio_dialogue_questions,
    "听对话选择题1v5": handle_audio_dialogue_questions,
    "句子排序题": handle_sentence_sorting,
    "阅读理解题1v2": handle_reading_1v2,
    "短文选词填空题5": handle_passage_filling5,
    "短文选词填空题6": handle_passage_filling6,
    "阅读文章选择题": handle_reading_multiple_choice,
    "长文本理解题": handle_long_text_comprehension,
    "短文选句填空题": handle_sentence_filling,
    "病句选择题": handle_sentence_error_choice,
    "文章选择题": handle_article_questions,
    "听短文选择题": handle_article_listening,

    # 其他题型处理器...
}


def display_questions(questions, level, category):
    """展示生成的题目，根据题型分发到不同的处理器"""
    for i, q in enumerate(questions, 1):
        with st.container():
            # 题型标题
            st.subheader(f"题目{i} | {q.get('type', '未知题型')}")

            # 根据题型选择对应的处理器
            question_type = q.get('type', '')
            handler = QUESTION_HANDLERS.get(question_type)

            if handler:
                # 调用对应的处理器
                handler(q, level, category, i)
            else:
                # 默认处理器或错误处理
                st.warning(f"未实现的题型处理逻辑：{question_type}")

            # 答案与解析
            with st.expander("查看答案与解析", expanded=False):
                st.success(f"正确答案：{q.get('answer', '无')}")
                if q.get("explanation"):
                    st.info(f"解析：{q['explanation']}")

            st.write("---")


if __name__ == "__main__":
    main()