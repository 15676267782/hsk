# -*- coding: utf-8 -*-
import json
import os

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
                "audio_content": "2-4个字词语",
                "min_words": 2,
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
                "min_words": 5,
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
                "min_words": 40,
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
                "min_words": 80,
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
                "min_words": 120,
                "max_options": 4,
                "vocab_level": 4,
                "vocab_weight_mode": True,  # 启用权重模式
            },
            "听对话选择题1v2": {
                "require_audio": True,
                "require_image": False,
                "audio_content": "一段对话材料，随后有2 - 3道选择题",
                "min_words": 150,
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
hsk6_grammar = """HSK6 对应国际中文教育中文水平等级标准的六级水平，是对学习者中文语法掌握的最高要求，注重在文学创作、学术研究等高层次场景中精准、灵活且富有表现力地运用语法。
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