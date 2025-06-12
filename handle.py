# -*- coding: utf-8 -*-
from util import *
from config import *
import uuid
import asyncio
import time


# 题型处理器 - 策略模式实现
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)


def handle_look_and_judge1(q, level, category, i,paper_display_id):
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
            # 修正：从数组中获取第一个描述
            image_desc = q.get("image_description", [q["content"]])[0]
            st.markdown("🖼️ **根据描述生成图像：**")

            # 添加调试信息
            st.write(f"发送到图像API的描述: {image_desc}")

            img_bytes = generate_image_from_text(image_desc)
            if img_bytes:
                st.image(img_bytes, width=200)
            else:
                st.warning("图像生成失败，使用默认占位图")
                st.image("https://picsum.photos/400/300", width=200)

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
                except Exception as e:
                    st.warning(f"无法清理临时文件: {str(e)}")


def handle_look_and_judge2(q, level, category, i,paper_display_id):
    """处理阅读看图判断题"""
    # 获取该题型的详细配置
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})

    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))  # 获取HSK数字等级

    st.write("调试：阅读看图判断题数据结构 =", q)

    try:
        # 处理图片部分
        if type_config.get("require_image", True):
            # 修正：从数组中获取第一个描述（如果存在）
            image_desc = q.get("image_description", [q["content"]])[0]
            st.markdown("🖼️ **根据描述生成图像：**")

            # # 添加调试信息
            # st.write(f"发送到图像API的描述: {image_desc}")

            img_bytes = generate_image_from_text(image_desc)
            if img_bytes:
                st.image(img_bytes, width=200)  # 优化图片显示
            else:
                st.warning("图像生成失败，使用默认占位图")
                st.image("https://picsum.photos/600/400", width=200)

        # 显示题目内容（根据HSK级别调整）
        if q.get('content'):
            adjusted_content = adjust_text_by_hsk(q['content'], hsk_num)
            st.markdown(f" {adjusted_content}")

        # 显示问题（如果有多个问题，逐个显示）
        if q.get("questions"):
            questions = q.get("questions", [])
            if isinstance(questions, str):  # 如果只有一个问题，包装成列表
                questions = [questions]

            for idx, question in enumerate(questions):
                adjusted_question = adjust_text_by_hsk(question, hsk_num)
                st.markdown(f"**问题{idx + 1}：** {adjusted_question}")

        # 显示选项（根据HSK级别调整）
        if q.get("options"):
            # 根据HSK等级调整选项词汇
            adjusted_options = [adjust_text_by_hsk(option, hsk_num) for option in q["options"]]

            if f'answer_{i}' not in st.session_state:
                st.session_state[f'answer_{i}'] = None

            # 优化选项显示和选择逻辑
            selected_option = st.radio(
                "请选择正确的答案：",
                adjusted_options,
                index=adjusted_options.index(st.session_state[f'answer_{i}'])
                if st.session_state[f'answer_{i}'] in adjusted_options else 0,
                key=f"options_{i}"
            )

            st.session_state[f'answer_{i}'] = selected_option

    except Exception as e:
        st.error(f"处理题目时发生错误: {str(e)}")


def handle_look_and_choice(q, level, category, i,paper_display_id):
    """处理看图选择题（修复图片生成问题）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write("调试：看图选择题数据结构 =", q)

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

        # 从options生成图片描述
        image_descriptions = []
        for j, option in enumerate(q.get("options", [])):
            # 提取选项文本（去除选项前缀）
            option_text = re.sub(r'^[A-Da-d]\.?\s*', '', option).strip()
            image_descriptions.append(option_text)

        # 生成并显示图片
        if image_descriptions:
            cols = st.columns(len(image_descriptions))
            for j, img_desc in enumerate(image_descriptions):
                img_bytes = generate_image_from_text(img_desc)
                if img_bytes:
                    cols[j].image(img_bytes, width=150)
                    # cols[j].caption(f"选项{chr(65 + j)}: {img_desc}")

    # 显示问题
    if q.get("question"):
        adjusted_question = adjust_text_by_hsk(q["question"], hsk_num)
        st.markdown(f"**问题：** {adjusted_question}")

    # 显示文本选项
    if q.get("options"):
        adjusted_options = [f"{chr(65 + j)}. {adjust_text_by_hsk(option, hsk_num)}"
                            for j, option in enumerate(q.get("options", []))]

        # 预初始化session_state
        answer_key = f'answer_{i}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = None

        # 创建单选框
        selected_option = st.radio(
            "请选择正确的答案：",
            adjusted_options,
            index=next(
                (idx for idx, opt in enumerate(adjusted_options)
                 if opt.startswith(f"{q.get('answer', 'A')}.")),
                0
            ),
            key=answer_key
        )

        # 存储答案（只在提交后处理，避免状态修改错误）
        if st.button("提交答案"):
            st.session_state[answer_key] = selected_option.split('.')[0].strip()

            # 显示结果
            correct_answer = q.get('answer', 'A')
            user_choice = st.session_state[answer_key]

            if user_choice == correct_answer:
                st.success("✓ 回答正确！")
            else:
                st.error(f"✗ 正确答案：{correct_answer}")

            if q.get("explanation"):
                st.info(f"解析：{q.get('explanation')}")


def handle_image_sorting(q, level, category, i,paper_display_id):
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    dialogues = q.get("dialogues", [])
    options = q.get("options", [])
    answers = q.get("answers", [])  # 假设answers是原始选项的正确索引（如["A", "B", "C"]对应原始顺序）

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

    # ----------------------- 新增：随机打乱选项顺序 -----------------------
    original_options = options.copy()  # 保存原始选项顺序
    random.shuffle(options)  # 打乱选项顺序
    option_indices = {char: idx for idx, char in
                      enumerate([chr(65 + k) for k in range(len(original_options))])}  # 原始选项字母索引

    # 生成随机选项与原始选项的映射（例如：打乱后的选项B对应原始选项A）
    shuffled_mapping = {new_char: original_char
                        for new_char, original_char in zip([chr(65 + k) for k in range(len(options))],
                                                           [chr(65 + k) for k in range(len(original_options))])}
    # ----------------------- 显示界面调整 -----------------------
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
            cols[k].image(img_bytes, caption=f"选项 {chr(65 + k)}")
        else:
            cols[k].markdown(f"{chr(65 + k)}. {option}")

    # 用户选择区域（处理随机映射）
    selected_order = []
    for j in range(len(dialogues)):
        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = ""  # 保存原始选项的正确字母（如"A"）

        # 显示打乱后的选项字母供用户选择
        shuffled_letters = [chr(65 + k) for k in range(len(options))]
        selected_shuffled_char = st.selectbox(
            f"请为对话 {j + 1} 选择对应的图片选项：",
            shuffled_letters,
            index=next(
                (idx for idx, opt in enumerate(shuffled_letters)
                 if opt == shuffled_mapping.get(st.session_state[answer_key], shuffled_letters[0])),  # 映射原始答案到打乱后的选项
                0
            ),
            key=f"sorting_{i}_{j}"
        )

        # 将用户选择的打乱字母转换为原始字母（例如：用户选的是打乱后的"B"，实际对应原始"A"）
        selected_original_char = next(
            original_char for original_char, shuffled_char in shuffled_mapping.items()
            if shuffled_char == selected_shuffled_char
        )
        selected_order.append(selected_original_char)
        st.session_state[answer_key] = selected_original_char  # 保存原始字母答案

    # 显示答案与解析
    with st.expander("查看答案与解析", expanded=False):
        st.success(f"正确的图片顺序：{' -> '.join(answers)}")
        explanation = q.get("explanations", [""])
        st.info(type_config.get('explanation_format', '').format(explanation=explanation))


def handle_listening(q, level, category, i,paper_display_id):
    """处理听力选择题（动态读取audio_content并自动分配男女声，删除冒号前的内容）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write("调试：听力选择题数据结构 =", q)

    # 使用UUID生成绝对唯一的键值后缀
    unique_suffix = str(uuid.uuid4())[:8]  # 取UUID的前8位作为后缀

    # 生成更唯一的键值前缀，包含级别、分类、题型、题号和内容哈希
    content_hash = str(hash(str(q.get("audio_content", ""))))[:8]  # 取哈希值的前8位
    unique_key_prefix = f"{level}_{category}_{q.get('type', '')}_{i}_{content_hash}_{unique_suffix}"

    # 提取题目信息
    audio_content = q.get("audio_content", [])  # 确保是列表
    question = q.get("audio_question", "")
    options = q.get("options", [])

    # 验证数据有效性
    if not audio_content:
        st.error("错误：未找到听力对话内容")
        return

    # 删除冒号及其前面的内容
    adjusted_contents = []
    original_contents = []  # 保留原始内容用于显示

    for text in audio_content:
        original_contents.append(text)

        # 删除冒号及其前面的所有内容
        cleaned_text = text.split('：')[-1].split(':')[-1].strip()
        adjusted_text = adjust_text_by_hsk(cleaned_text, hsk_num)
        adjusted_contents.append(adjusted_text)

    adjusted_question = adjust_text_by_hsk(question, hsk_num)
    adjusted_options = [adjust_text_by_hsk(option, hsk_num) for option in options]

    # 动态生成所有音频文件
    audio_files = []
    voice_types = ['female', 'male']  # 轮流使用女声和男声

    try:
        # 为每个对话内容生成音频
        for idx, (content, original) in enumerate(zip(adjusted_contents, original_contents)):
            # 根据索引确定使用男声还是女声（交替使用）
            voice = voice_types[idx % len(voice_types)]
            icon = "👩" if voice == 'female' else "👨"

            # 生成临时音频文件
            audio_file = f"temp_{voice}_{uuid.uuid4().hex}.mp3"
            asyncio.run(text_to_speech(content, audio_file, level, voice=voice))

            # 记录音频文件和相关信息
            audio_files.append({
                'file': audio_file,
                'voice': voice,
                'icon': icon,
                'content': content,
                'original': original  # 保留原始带前缀的内容用于显示
            })

            # st.write(f"{icon} 正在生成：{original[:30]}...")

        # 生成问题音频（使用女声）
        question_audio = f"temp_question_{uuid.uuid4().hex}.mp3"
        asyncio.run(text_to_speech(adjusted_question, question_audio, level, voice='female'))

        # 合并所有对话音频
        combined_audio = f"temp_combined_{uuid.uuid4().hex}.mp3"
        combine_audio_files([item['file'] for item in audio_files], combined_audio)

        # 显示音频播放器
        st.markdown("🎧 **听力内容（完整对话）：**")
        play_audio_in_streamlit(combined_audio)

        # 显示分段音频（带原始前缀信息）
        with st.expander("查看分段音频"):
            for item in audio_files:
                st.markdown(f"{item['icon']} **{item['original']}**")
                play_audio_in_streamlit(item['file'])

        st.markdown("**问题：**")
        play_audio_in_streamlit(question_audio)

    except Exception as e:
        st.error(f"生成或播放录音时出错: {str(e)}")
    finally:
        # 确保所有临时文件都被记录以便清理
        if 'temp_files' not in st.session_state:
            st.session_state.temp_files = []
        st.session_state.temp_files.extend([item['file'] for item in audio_files])

    # 显示问题和选项
    if f'answer_{unique_key_prefix}' not in st.session_state:
        st.session_state[f'answer_{unique_key_prefix}'] = None

    selected_option = st.radio(
        "请选择正确的答案：",
        adjusted_options,  # 直接使用原始选项列表，无需添加字母前缀
        index=adjusted_options.index(st.session_state[f'answer_{unique_key_prefix}'])
        if st.session_state[f'answer_{unique_key_prefix}'] in adjusted_options else 0,
        key=f"listening_options_{unique_key_prefix}"
    )

    st.session_state[f'answer_{unique_key_prefix}'] = selected_option

    # 提交答案按钮 - 使用更唯一的键值
    if st.button("提交答案", key=f"submit_{unique_key_prefix}"):
        correct_answer = q.get("answer", "A")
        user_choice = selected_option.split('.')[0].strip()

        if user_choice == correct_answer:
            st.success("✅ 回答正确！")
        else:
            st.error(f"❌ 正确答案是：{correct_answer}")

        # 显示解析（如果有）
        if q.get("explanation"):
            st.info(f"解析：{q.get('explanation')}")

def handle_fill_in_the_blank(q, level, category, i,paper_display_id):
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
            adjusted_sentences.append(f"{pinyin_text}")
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
    # 显示选项（无字母前缀，横向排列）
    st.markdown("### 选项：")

    # 创建一行多列布局，每个选项占一列
    cols = st.columns(len(adjusted_options))
    for j, opt in enumerate(adjusted_options):
        with cols[j]:
            st.markdown(f"{opt}")  # 使用圆点代替字母标识

    # ------------------------------
    # 4. 答案选择（改为下拉选择形式）
    # ------------------------------
    # ------------------------------
    # 4. 答案选择（仅显示字母ABCD，存储字母答案）
    # ------------------------------
    user_answers = {}
    option_letters = [chr(65 + j) for j in range(len(adjusted_options))]  # 生成字母列表[A, B, C, D, E]

    for idx in range(len(sentences)):
        key = f"fill_answer_{i}_{idx}"

        # 使用下拉框显示字母选项，并关联原始选项文本
        user_letter = st.selectbox(
            f"请为第{idx + 1}题选择答案",
            option_letters,  # 显示字母A-E
            key=key
        )

        # 存储用户选择的字母（如"A", "B"）
        user_answers[idx + 1] = user_letter

    # ------------------------------
    # 5. 提交与结果验证（根据字母索引匹配选项）
    # ------------------------------
    if st.button(f"提交答案", key=f"submit_fill_{i}"):
        correct_count = 0
        correct_letters = q.get("answers", [])  # 假设正确答案为字母列表（如 ["A", "B", "C"]）

        for question_id, user_letter in user_answers.items():
            idx = question_id - 1
            if idx < len(correct_letters):
                correct_letter = correct_letters[idx].upper()

                # 根据字母索引获取选项文本（用于显示）
                user_option_idx = ord(user_letter) - 65  # A->0, B->1...
                user_option_text = adjusted_options[user_option_idx] if user_option_idx < len(adjusted_options) else ""

                # 根据正确答案字母获取正确选项文本（用于显示）
                correct_option_idx = ord(correct_letter) - 65
                correct_option_text = adjusted_options[correct_option_idx] if correct_option_idx < len(
                    adjusted_options) else ""

                with st.expander(f"第{question_id}题 结果"):
                    st.markdown(f"**题目：** {sentences[idx]}")
                    st.markdown(f"**你的答案：** {user_letter} ({user_option_text})")
                    st.markdown(
                        f"**正确答案：** {correct_letter} ({correct_option_text}) {'✅' if user_letter == correct_letter else '❌'}")

                    if user_letter != correct_letter:
                        st.info(f"解析：此处应选 {correct_letter}，因为...")  # 可添加自定义解析

        total = len(sentences)
        score = f"{correct_count}/{total}"
        st.success(f"得分：{score} ({correct_count / total:.0%})")

def handle_text_judgment1(q, level, category, i,paper_display_id):
    """处理文字判断题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write(q)

    # 提取题目信息
    audio_content = q.get("audio_content", "")
    target_sentence = q.get("target_sentence", "")
    options = type_config.get("options", ["对", "错"])

    # 调整词汇
    adjusted_audio_content = adjust_text_by_hsk(audio_content, hsk_num)
    adjusted_target_sentence = adjust_text_by_hsk(target_sentence, hsk_num)

    # 播放原始录音
    st.markdown("🎧 **点击播放描述录音：**")
    temp_audio = f"temp_description_{uuid.uuid4().hex}.mp3"
    try:
        asyncio.run(text_to_speech(adjusted_audio_content, temp_audio, level))
        play_audio_in_streamlit(temp_audio)
    except Exception as e:
        st.error(f"生成描述录音时出错: {str(e)}")
    finally:
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

    # 显示问题文本
    st.markdown("### 问题：")
    st.markdown(f"请判断 **※{adjusted_target_sentence}※** 是否正确")
    # # 生成并播放目标句子音频
    # st.markdown("🎧 **点击播放目标句子录音：**")
    temp_target_audio = f"temp_target_{uuid.uuid4().hex}.mp3"
    try:
        # 调整目标句子词汇并生成音频
        adjusted_target_for_audio = adjust_text_by_hsk(target_sentence, hsk_num)
        asyncio.run(text_to_speech(adjusted_target_for_audio, temp_target_audio, level))
        play_audio_in_streamlit(temp_target_audio)
    except Exception as e:
        st.error(f"生成目标句子录音时出错: {str(e)}")
    finally:
        if os.path.exists(temp_target_audio):
            os.remove(temp_target_audio)
    # 显示选项
    if f'answer_{i}' not in st.session_state:
        st.session_state[f'answer_{i}'] = None

    selected_option = st.radio(
        "请选择：",
        options,
        index=options.index(st.session_state[f'answer_{i}']) if st.session_state[f'answer_{i}'] in options else 0,
        key=f"judgment_options_{i}"
    )

    st.session_state[f'answer_{i}'] = selected_option

def handle_sentence_matching1(q, level, category, i,paper_display_id):
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


        # 为每个问题创建独立的选择
        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = answers[j] if j < len(answers) else ""

        option_labels = [
            f"{opt['label']}. {opt['pinyin']}"
            for opt in adjusted_options
        ]



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


def handle_text_judgment2(q, level, category, i,paper_display_id):
    """处理阅读判断题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write(q)

    # 提取题目信息
    content = q.get("content", "")  # 阅读文本
    questions = q.get("questions", [])  # 需要判断的问题列表
    answers = q.get("answer", [])  # 正确答案列表
    explanation = q.get("explanation", "")  # 答案解析

    # 确保有问题可显示
    if not questions or not isinstance(questions, list):
        st.error("题目数据错误：questions字段应为非空列表")
        return

    # 只处理第一个问题（当前设计只显示一个问题）
    if len(questions) > 0:
        question = questions[0]
        answer = answers[0] if isinstance(answers, list) and len(answers) > 0 else ""
    else:
        st.error("题目数据错误：questions列表为空")
        return

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
    st.markdown(f"*{question_with_pinyin}*")

    # 显示选项
    options = type_config.get("options", ["对", "错"])

    answer_key = f'answer_{i}'

    # 确保session_state中的值是有效选项
    if answer_key not in st.session_state or st.session_state[answer_key] not in options:
        # 设置默认值为正确答案或选项列表的第一个值
        st.session_state[answer_key] = answer if answer in options else options[0]

    selected_option = st.radio(
        "请选择：",
        options,
        index=options.index(st.session_state[answer_key]),  # 确保索引有效
        key=f"judgment_{i}"
    )

    st.session_state[answer_key] = selected_option

def handle_sentence_matching2(q, level, category, i,paper_display_id):
    """处理句子匹配题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))
    min_words = type_config.get("min_words")  # 获取最小字数
    st.write(q)

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


def handle_reading_comprehension(q, level, category, i,paper_display_id):
    """处理阅读理解题"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write(q)

    # 处理文章段落
    passages = q.get("passages", [])
    if isinstance(passages, str):
        st.warning("注意：passages字段应为列表，已将字符串转换为列表")
        passages = [passages]

    # 处理问题列表
    questions = q.get("questions", [])
    all_options = q.get("options", [])  # 所有问题的选项
    answers = q.get("answer", "")  # 答案

    # 显示文章
    st.markdown("### 阅读文章：")
    for passage in passages:
        adjusted_passage = adjust_text_by_hsk(passage, hsk_num)
        st.markdown(adjusted_passage)

    # 显示问题和选项
    st.markdown(f"### {type_config.get('question_format', '根据短文内容，回答问题：')}")

    # 遍历每个问题
    for j, question_text in enumerate(questions, 1):
        # 获取当前问题的选项
        if isinstance(all_options, list) and j <= len(all_options) and isinstance(all_options[j - 1], list):
            # 嵌套选项格式 - 每个问题有独立的选项列表
            options = all_options[j - 1]
        else:
            # 扁平选项格式 - 所有问题共享同一组选项
            options = all_options

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

        # 获取正确答案（假设answers是字符串，如"CBB"）
        correct_answer = answers[j - 1] if j <= len(answers) else ""

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

    # 添加提交按钮和结果显示
    if st.button("提交答案", key=f"submit_{i}"):
        correct_count = 0
        for j, question_text in enumerate(questions, 1):
            answer_key = f'answer_{i}_{j}'
            user_answer = st.session_state.get(answer_key, "")
            correct_answer = answers[j - 1] if j <= len(answers) else ""

            with st.expander(f"问题 {j} 的结果"):
                st.markdown(f"**问题：** {question_text}")
                st.markdown(f"**你的答案：** {user_answer}")
                st.markdown(f"**正确答案：** {correct_answer}")

                if user_answer == correct_answer:
                    st.success("✅ 正确")
                    correct_count += 1
                else:
                    st.error("❌ 错误")

        total = len(questions)
        score = f"{correct_count}/{total}"
        st.markdown(f"### 得分：{score} ({correct_count / total:.0%})")


def handle_image_matching(q, level, category, i,paper_display_id):
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write(q)  # 调试输出

    # 获取图片描述（使用image_description字段而非sentences）
    image_descriptions = q.get("image_description", [])
    options = q.get("options", [])
    answers = q.get("answer", [])  # 注意：您的数据中answer是字符串，可能需要调整

    st.markdown(f"### {type_config.get('question_format', '请将图片与对应的描述匹配')}")

    # 确保有图片描述
    if not image_descriptions:
        st.error("题目数据错误：缺少image_description字段")
        return

    # 显示所有图片描述（调整HSK级别并添加拼音）
    for j, desc in enumerate(image_descriptions):
        adjusted_desc = adjust_text_by_hsk(desc, hsk_num)

        # 添加拼音支持
        if type_config.get("show_pinyin", True):
            pinyin_desc = add_pinyin(adjusted_desc)  # 假设add_pinyin函数存在
            st.markdown(f"**句子{j+1}：** {pinyin_desc}")
        else:
            st.markdown(f"**句子{j+1}：** {adjusted_desc}")

    st.markdown("### 图片")
    images_per_row = min(5, len(image_descriptions))  # 每行最多显示5张图片

    for row_idx in range(0, len(image_descriptions), images_per_row):
        cols = st.columns(images_per_row)
        for col_idx, img_idx in enumerate(range(row_idx, min(row_idx + images_per_row, len(image_descriptions)))):
            desc = image_descriptions[img_idx]
            adjusted_desc = adjust_text_by_hsk(desc, hsk_num)

            try:
                # 尝试生成图片
                img_bytes = generate_image_from_text(adjusted_desc)
                if img_bytes:
                    cols[col_idx].image(img_bytes, caption=f"图片 {chr(65 + img_idx)}", use_column_width=True)
                else:
                    raise Exception("图片生成失败")
            except Exception as e:
                cols[col_idx].error(f"无法生成图片 {chr(65 + img_idx)}: {str(e)}")
                # 使用占位图替代
                cols[col_idx].image("https://picsum.photos/300/200",
                                    caption=f"图片 {chr(65 + img_idx)}(占位图)",
                                    use_column_width=True)

    # 显示选项（调整HSK级别）
    st.markdown("### 选项")

    # 提取选项文本（移除字母前缀）
    cleaned_options = []
    for opt in options:
        if isinstance(opt, str) and len(opt) > 2 and opt[1] == '.':
            cleaned_options.append(opt[2:].strip())  # 移除字母前缀
        else:
            cleaned_options.append(opt)

    # 调整选项的HSK级别
    adjusted_options = [adjust_text_by_hsk(opt, hsk_num) for opt in cleaned_options]

    # 确保有足够的选项
    if len(adjusted_options) < len(image_descriptions):
        st.warning(f"警告：选项数量({len(adjusted_options)})少于图片数量({len(image_descriptions)})")

    user_answers = {}
    for j in range(len(image_descriptions)):
        letter_index = chr(65 + j)  # 使用字母索引
        answer_key = f'answer_{i}_{j}'

        if answer_key not in st.session_state:
            st.session_state[answer_key] = 'A'  # 默认选择A（如果有选项）

        # 使用字母作为选项（A, B, C, D, E）
        option_letters = [chr(65 + k) for k in range(len(adjusted_options))]

        # 确保session_state中的值是有效的字母选项
        if st.session_state[answer_key] not in option_letters and option_letters:
            st.session_state[answer_key] = option_letters[0]

        # 使用下拉菜单选择字母选项
        selected_letter = st.selectbox(
            f"请为图片 {letter_index} 选择匹配的描述编号：",
            option_letters,
            index=option_letters.index(st.session_state[answer_key])
            if st.session_state[answer_key] in option_letters else 0,
            key=f"matching_{i}_{j}"
        )

        user_answers[j] = selected_letter

    # 提交答案按钮
    if st.button("提交答案", key=f"submit_matching_{i}"):
        correct_count = 0

        # 检查答案格式（可能是字符串或列表）
        if isinstance(answers, str):
            answers_list = list(answers)  # 将字符串转为列表（如 "B" → ['B']）
        else:
            answers_list = answers

        # 验证每个答案
        for j in range(len(image_descriptions)):
            letter_index = chr(65 + j)  # 图片字母索引
            user_answer = user_answers[j]  # 用户选择的字母

            # 获取正确答案
            if j < len(answers_list):
                correct_answer = answers_list[j].upper()

                with st.expander(f"图片 {letter_index} 的结果"):
                    st.markdown(f"**你的选择：** {user_answer}")
                    st.markdown(f"**正确答案：** {correct_answer}")

                    # 获取选项文本用于显示
                    if user_answer:
                        user_option_idx = ord(user_answer) - ord('A')
                        user_option_text = adjusted_options[user_option_idx] if user_option_idx < len(
                            adjusted_options) else ""
                        st.markdown(f"**你选择的描述：** {user_option_text}")

                    if correct_answer:
                        correct_option_idx = ord(correct_answer) - ord('A')
                        correct_option_text = adjusted_options[correct_option_idx] if correct_option_idx < len(
                            adjusted_options) else ""
                        st.markdown(f"**正确描述：** {correct_option_text}")

                    if user_answer == correct_answer:
                        st.success("✅ 正确")
                        correct_count += 1
                    else:
                        st.error("❌ 错误")

        # 显示得分
        total = len(image_descriptions)
        st.markdown(f"### 得分：{correct_count}/{total} ({correct_count / total:.0%})")

    # 查看答案与解析
    with st.expander("查看答案与解析", expanded=False):
        # 检查答案格式
        if isinstance(answers, str):
            answers_list = list(answers)  # 将字符串转为列表
        else:
            answers_list = answers

        for j in range(len(image_descriptions)):
            letter_index = chr(65 + j)  # 使用字母索引

            if j < len(answers_list):
                correct_letter = answers_list[j].upper()
                correct_index = ord(correct_letter) - ord('A')

                if 0 <= correct_index < len(cleaned_options):
                    correct_answer_text = f"{correct_letter}. {cleaned_options[correct_index]}"
                    st.success(f"图片 {letter_index} 的正确答案：{correct_answer_text}")

                    # 显示解析（如果有）
                    explanations = q.get("explanation", [])
                    if isinstance(explanations, list) and j < len(explanations):
                        st.info(explanations[j])
                    elif isinstance(explanations, str):
                        st.info(explanations)


def handle_image_matching2(q, level, category, i,paper_display_id):
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write(q)  # 调试输出

    sentences = q.get("sentences", [])
    options = q.get("options", [])
    answers = q.get("answers", [])

    st.markdown(f"### {type_config.get('question_format', '请将句子与对应的图片描述匹配')}")

    # 显示所有句子（调整HSK级别）
    for j, sentence in enumerate(sentences):
        adjusted_sentence = adjust_text_by_hsk(sentence, hsk_num)
        st.markdown(f"**句子 {j + 1}：** {adjusted_sentence}")

    st.markdown("### 图片")
    images_per_row = 5
    for row_idx in range(0, len(sentences), images_per_row):
        cols = st.columns(images_per_row)
        for col_idx, sentence_idx in enumerate(range(row_idx, min(row_idx + images_per_row, len(sentences)))):
            sentence = sentences[sentence_idx]
            adjusted_sentence = adjust_text_by_hsk(sentence, hsk_num)  # 调整HSK级别

            img_bytes = generate_image_from_text(adjusted_sentence)  # 使用调整后的文本生成图片
            if img_bytes:
                cols[col_idx].image(img_bytes, caption=f"图片 {sentence_idx + 1}", width=200)
            else:
                cols[col_idx].error(f"无法生成句子 {sentence_idx + 1} 的图片")
                cols[col_idx].image("https://picsum.photos/200/200", caption=f"图片 {sentence_idx + 1} (占位图)", width=200)

    # 显示选项（调整HSK级别）
    st.markdown("### 选项")
    adjusted_options = [adjust_text_by_hsk(opt, hsk_num) for opt in options]  # 调整所有选项的HSK级别

    for j in range(len(sentences)):
        answer_key = f'answer_{i}_{j}'
        if answer_key not in st.session_state:
            st.session_state[answer_key] = ""

        # 直接使用调整后的选项文本，不添加字母前缀
        selected_option = st.radio(
            f"请为句子 {j + 1} 选择匹配的图片描述：",
            adjusted_options,  # 直接使用调整后的选项列表
            index=adjusted_options.index(st.session_state[answer_key])
            if st.session_state[answer_key] in adjusted_options else 0,
            key=f"matching_{i}_{j}"
        )

        # 直接存储选项文本，无需解析字母
        st.session_state[answer_key] = selected_option

    with st.expander("查看答案与解析", expanded=False):
        for j, correct_answer in enumerate(answers):
            st.success(f"句子 {j + 1} 的正确答案：{correct_answer}")
            explanation = q.get("explanations", [""])[j]
            st.info(type_config.get('explanation_format', '').format(explanation=explanation))


def handle_connect_words_into_sentence(q, level, category, i,paper_display_id):
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = get_hsk_level(level)  # 获取HSK级别

    words = q.get("words", [])  # 待连成句子的词语列表
    correct_answer = q.get("answer", "")  # 正确答案（完整句子）
    explanation = q.get("explanation", "")  # 答案解析

    st.markdown(f"### {type_config.get('question_format', '请将下列词语连成一个完整的句子：')}")

    # 随机打乱词语顺序（新增功能）
    shuffled_words = words.copy()
    random.shuffle(shuffled_words)

    # 显示词语，根据配置决定是否显示拼音，并使用HSK级别调整难度
    word_display = []
    for word in shuffled_words:
        adjusted_word = adjust_text_by_hsk(word, hsk_num)  # 调整词语难度
        if type_config.get("show_pinyin", False):
            word_display.append(add_pinyin(adjusted_word))
        else:
            word_display.append(adjusted_word)

    st.markdown(", ".join(word_display), unsafe_allow_html=True)  # 用逗号连接词语

    # 让用户输入连成的句子
    answer_key = f'answer_{i}'

    # 初始化session_state值
    if answer_key not in st.session_state:
        st.session_state[answer_key] = ""

    # 获取用户输入
    user_answer = st.text_input(
        "请输入连成的句子",
        value=st.session_state[answer_key],
        key=answer_key
    )

    # 答案验证（新增逻辑）
    if st.button("提交答案"):
        # 使用HSK级别调整正确答案（确保难度匹配）
        adjusted_correct_answer = adjust_text_by_hsk(correct_answer, hsk_num)

        # 简单验证（去除空格和标点后比较）
        user_cleaned = user_answer.replace(" ", "").replace("，", ",").replace("。", "")
        correct_cleaned = adjusted_correct_answer.replace(" ", "").replace("，", ",").replace("。", "")

        if user_cleaned == correct_cleaned:
            st.success("✅ 回答正确！")
        else:
            st.error(f"❌ 回答错误，正确答案是：{adjusted_correct_answer}")

        # 显示答案解析（如果有）
        if explanation:
            adjusted_explanation = adjust_text_by_hsk(explanation, hsk_num)
            st.markdown(f"**解析：** {adjusted_explanation}", unsafe_allow_html=True)


def handle_audio_dialogue_questions(q, level, category, i,paper_display_id):
    """处理听对话录音题（删除冒号前的内容，动态生成音频）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 4))

    st.write(q)

    # 提取听力材料和问题列表
    audio_content = q.get("audio_content", [])
    questions_data = q.get("questions", [])

    # 确保audio_content是列表
    if not isinstance(audio_content, list):
        if isinstance(audio_content, str):
            # 按常见分隔符分割字符串
            audio_content = re.split(r'[。？！\n]', audio_content)
            audio_content = [s.strip() for s in audio_content if s.strip()]
        else:
            st.error(f"无法处理audio_content类型: {type(audio_content)}")
            return

    if not audio_content:
        st.error("错误：缺少对话内容")
        return

    if not questions_data:
        st.error("错误：缺少问题数据")
        return

    # 删除冒号及其前面的内容
    adjusted_contents = []
    original_contents = []

    for text in audio_content:
        original_contents.append(text)

        # 删除冒号及其前面的所有内容
        cleaned_text = text.split('：')[-1].split(':')[-1].strip()
        adjusted_text = adjust_text_by_hsk(cleaned_text, hsk_num)
        adjusted_contents.append(adjusted_text)

    # 使用上下文管理器管理临时文件
    with manage_temp_files() as temp_files:
        # 动态生成所有音频文件
        audio_files = []
        voice_types = ['female', 'male']  # 轮流使用女声和男声

        # 为每个对话内容生成音频
        for idx, (content, original) in enumerate(zip(adjusted_contents, original_contents)):
            # 根据索引确定使用男声还是女声（交替使用）
            voice = voice_types[idx % len(voice_types)]
            icon = "👩" if voice == 'female' else "👨"

            # 生成临时音频文件
            audio_file = f"temp_{voice}_{uuid.uuid4().hex}.mp3"
            temp_files.append(audio_file)

            try:
                asyncio.run(text_to_speech(content, audio_file, level, voice=voice))
            except Exception as e:
                st.error(f"生成第{idx + 1}句音频时出错: {str(e)}")
                continue

            # 记录音频文件和相关信息
            audio_files.append({
                'file': audio_file,
                'voice': voice,
                'icon': icon,
                'content': content,
                'original': original,
                'index': idx + 1
            })

        # 合并所有对话音频
        if not audio_files:
            st.error("没有生成任何音频文件")
            return

        combined_audio = f"temp_combined_{uuid.uuid4().hex}.mp3"
        temp_files.append(combined_audio)

        try:
            combine_audio_files([item['file'] for item in audio_files], combined_audio)
        except Exception as e:
            st.error(f"合并音频时出错: {str(e)}")
            return

        # 显示音频播放器
        st.markdown("🎧 **听力内容（完整对话）：**")
        play_audio_in_streamlit(combined_audio)

        # 显示分段音频
        with st.expander("查看分段音频"):
            for item in audio_files:
                st.markdown(f"{item['icon']} **第{item['index']}句：{item['original']}**")
                play_audio_in_streamlit(item['file'])

        # 处理每个问题
        user_answers = {}

        for j, question_data in enumerate(questions_data):
            # 提取问题信息
            question_id = question_data.get("id", j + 1)
            question_text = question_data.get("text", f"问题{question_id}")
            options = question_data.get("options", [])
            answer = question_data.get("answer", "")
            explanation = question_data.get("explanation", "")

            if not options:
                st.warning(f"警告：问题 {question_id} 缺少选项")
                continue

            # 生成问题音频
            question_audio_file = f"temp_question_{question_id}_{uuid.uuid4().hex}.mp3"
            temp_files.append(question_audio_file)

            question_audio_enabled = question_data.get("audio_enabled", type_config.get("question_audio_enabled", True))

            # 问题容器
            with st.container():
                st.markdown(f"### **问题 {question_id}：**")

                # 直接显示问题音频
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
                option_labels = [f"{opt}" for opt in options]

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

def handle_sentence_sorting(q, level, category, i,paper_display_id):
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

def handle_passage_filling5(q, level, category, i,paper_display_id):
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
            "选项：",  # 这里的标签文本可以自定义或隐藏
            adjusted_options,  # 直接使用选项列表，无需添加字母前缀
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

def handle_passage_filling6(q, level, category, i,paper_display_id):
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

def handle_reading_multiple_choice(q, level, category, i,paper_display_id):
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
            f"**问题 {j}：{adjusted_q}**",
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


def handle_long_text_comprehension(q, level, category, i,paper_display_id):
    """处理长文本理解题（修复嵌套列表格式的选项）"""
    config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get("长文本理解题", {})
    hsk_num = q.get("vocab_level", config.get("vocab_level", 4))

    st.write("调试：长文本理解题数据结构 =", q)

    # 获取长文本内容
    text = q.get("text", "")
    if not text.strip():
        text = q.get("passage", "")
        text = q.get("content", text)  # 使用 content 字段

    # 处理列表类型的文本
    if isinstance(text, list):
        st.warning("注意：长文本内容是列表类型，尝试提取文本")
        if len(text) > 0 and isinstance(text[0], str):
            # 检查列表元素是否包含索引前缀（如 "0: "）
            if text[0].startswith(("0:", "1:", "2:")):
                # 提取冒号后的内容
                text = " ".join([item.split(":", 1)[1].strip() for item in text if isinstance(item, str)])
            else:
                text = " ".join(text)
        else:
            text = ""

    if not text.strip():
        st.error("错误：长文本内容为空")
        return

    # 获取问题列表（适配您的扁平化数据结构）
    questions = []

    # 检查是否是旧格式（问题和选项在顶级字段）
    if "question" in q or "questions" in q and isinstance(q["questions"], list) and len(q["questions"]) > 0:
        st.warning("注意：检测到旧格式的长文本问题数据，已自动转换为新格式")

        # 获取问题文本
        if "question" in q:
            question_text = q["question"]
        else:
            question_text = q["questions"][0]  # 使用第一个问题文本

        # 获取选项
        options = q.get("options", [])

        # 处理嵌套列表格式的options
        if options and isinstance(options[0], list):
            options = options[0]

        # 创建问题字典
        questions = [{
            "text": question_text,
            "options": options,
            "answer": q.get("answer", ""),
            "explanation": q.get("explanation", "")
        }]
    else:
        # 尝试使用questions字段（如果是新格式）
        questions = q.get("questions", [])

    # 验证问题数量
    if not questions:
        st.error("错误：未找到问题")
        return

    if len(questions) < config.get("min_questions", 1):
        st.error(f"错误：至少需要{config.get('min_questions', 1)}个问题")
        return

    # 显示长文本
    st.markdown("### 阅读材料：")
    adjusted_text = adjust_text_by_hsk(text, hsk_num)
    paragraphs = adjusted_text.split('\n\n')
    for para in paragraphs:
        if para.strip():
            st.markdown(para)
            st.markdown("")

    # 显示问题
    st.markdown(f"### {config.get('question_format', '根据文章内容，回答问题：')}")

    # 处理每个问题
    for j, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            st.error(f"问题 {j} 格式错误：应为字典，实际为{type(question)}")
            continue

        # 获取问题文本
        question_text = question.get("text", f"问题 {j}")
        if isinstance(question_text, list):
            question_text = " ".join(question_text).strip()

        if not question_text.strip():
            st.error(f"问题 {j} 的文本为空")
            question_text = f"问题 {j}（文本缺失）"

        # 获取选项
        options = question.get("options", [])

        # 处理嵌套列表格式的options
        if options and isinstance(options[0], list):
            st.warning(f"问题 {j} 的options是嵌套列表，已自动展平")
            options = options[0]

        if not options:
            st.error(f"问题 {j} 的选项为空")
            options = ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"]

        # 格式化选项（可选：如果您不需要自动添加字母前缀）
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

        # 创建单选组件
        answer_key = f"long_text_answer_{i}_{j}"
        selected_option = st.radio(
            f"问题 {j}: {question_text}",
            formatted_options,
            key=answer_key
        )

    # 提交按钮及结果验证
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

def handle_sentence_filling(q, level, category, i,paper_display_id):
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
        st.markdown(f"**第 {gap_number} 题**：{gap_format.format(gap_number=gap_number)}______")
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

def handle_sentence_error_choice(q, level, category, i,paper_display_id):
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

    # 创建单选组件（无字母前缀）
    answer_key = f"error_choice_{i}"
    selected_option = st.radio(
        "请选择答案：",
        options,  # 直接使用原始选项列表，无需添加字母前缀
        key=answer_key
    )

    # 提交按钮
    if st.button(f"提交答案", key=f"submit_error_{i}"):
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

def handle_reading_1v2(q, level, category, i,paper_display_id):
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


def handle_article_questions(q, level, category, i,paper_display_id):
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
        explanation = question.get("explanation", "")  # 提前获取解析文本

        # 显示问题和选项
        st.markdown(f"**问题 {q_id}：** {q_text}")
        selected = st.radio(
            "选项：",
            options,
            key=f"article_q_{i}_{q_id}"
        )

        # 提取用户选择的字母（改进版）
        user_letter = selected.split('.')[0].strip().upper()  # 从选项文本中提取字母（如"A"）

        user_answers.append({
            "question_id": q_id,
            "user_answer": user_letter,  # 使用提取的字母
            "correct_answer": correct_answer,
            "explanation": explanation  # 存储解析文本
        })

    # ------------------------------
    # 4. 提交答案和验证
    # ------------------------------
    if st.button(f"提交答案", key=f"submit_article_{i}"):
        correct_count = 0
        results = []  # 初始化results列表

        for ans in user_answers:
            user_ans = ans["user_answer"]
            is_correct = user_ans == ans["correct_answer"]

            results.append({
                "question_id": ans["question_id"],
                "is_correct": is_correct,
                "correct_answer": ans["correct_answer"],
                "explanation": ans["explanation"]  # 从user_answers获取解析
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
                st.markdown(f"**问题 {res['question_id']}**：{'✅ 正确' if res['is_correct'] else '❌ 错误'}")
                st.markdown(f"**解析**：{res['explanation']}")
                st.markdown("---")

def handle_article_listening(q, level, category, i,paper_display_id):
    """处理听短文选择题（问题带音频）"""
    type_config = DETAILED_QUESTION_CONFIG.get(level, {}).get(category, {}).get(q.get('type', ''), {})
    hsk_num = q.get("vocab_level", type_config.get("vocab_level", 6))

    st.write("调试：文章选择题数据结构 =", q)

    # 提取题目信息
    article_content = q.get("audio_content", [])  # 假设为句子列表
    questions = q.get("questions", [])
    audio_question = q.get("audio_question", "请听问题")  # 新增问题音频内容

    # 处理文章内容（假设需要分句处理）
    adjusted_article = [adjust_text_by_hsk(sentence, hsk_num) for sentence in article_content]


    # 生成文章音频（按句子分段生成，合并播放）
    st.markdown("🎧 **请听文章：**")
    article_audio_files = []
    combined_article_audio = f"temp_article_combined_{uuid.uuid4().hex}.mp3"

    try:
        # 生成每句话的音频并合并
        for idx, sentence in enumerate(adjusted_article):
            audio_file = f"temp_article_{idx}_{uuid.uuid4().hex}.mp3"
            asyncio.run(text_to_speech(sentence, audio_file, level, voice='male'))
            article_audio_files.append(audio_file)

        # 合并文章音频
        combine_audio_files(article_audio_files, combined_article_audio)
        play_audio_in_streamlit(combined_article_audio)

        # 显示文章文本
        if type_config.get("show_audio_text", False):
            with st.expander("查看文章原文"):
                st.markdown("\n".join(adjusted_article))

    except Exception as e:
        st.error(f"生成文章音频时出错: {str(e)}")
    finally:
        st.session_state.temp_files.extend(article_audio_files + [combined_article_audio])

    # 生成问题音频
    st.markdown("🎧 **请听问题：**")
    question_audio_files = []
    for j, question_data in enumerate(questions):
        question_text = question_data["question"]
        adjusted_question = adjust_text_by_hsk(question_text, hsk_num)
        audio_file = f"temp_question_{i}_{j}_{uuid.uuid4().hex}.mp3"

        try:
            asyncio.run(text_to_speech(adjusted_question, audio_file, level, voice='female'))
            question_audio_files.append(audio_file)
        except Exception as e:
            st.error(f"生成问题{j + 1}音频时出错: {str(e)}")

    # 显示问题和选项
    st.markdown("### ❓ **问题与选项：**")
    user_answers = {}

    for j, question_data in enumerate(questions):
        question_key = f'article_{i}_q{j}'
        question_text = question_data["question"]
        options = question_data["options"]

        # 播放问题音频
        st.markdown(f"#### **问题{j + 1}：**")
        st.audio(question_audio_files[j], format="audio/mp3", start_time=0)

        # 保存用户答案
        if question_key not in st.session_state:
            st.session_state[question_key] = None

        # st.markdown(f"**{question_text}**")
        selected_option = st.radio(
            f"请选择问题{j + 1}的答案：",
            options,
            index=options.index(st.session_state[question_key]) if st.session_state[question_key] in options else 0,
            key=f"article_{i}_options_{j}"
        )

        st.session_state[question_key] = selected_option
        user_answers[j] = selected_option

    # 提交答案逻辑（保持不变）
    if st.button("提交答案"):
        correct_count = 0
        results = []

        for j, question_data in enumerate(questions):
            user_choice = user_answers[j].split('.')[0].strip()
            correct_answer = question_data["answer"]
            is_correct = user_choice == correct_answer
            correct_count += 1 if is_correct else 0

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
            if result["explanation"]:
                st.info(f"解析：{result['explanation']}")


# 题型处理器映射
QUESTION_HANDLERS = {
    "听力看图判断题": handle_look_and_judge1,
    "阅读看图判断题": handle_look_and_judge2,
    "看图选择题": handle_look_and_choice,
    "图片排序题": handle_image_sorting,
    "听录音选择题": handle_listening,
    "选词填空题": handle_fill_in_the_blank,
    "图片匹配题": handle_image_matching,
    "图片匹配题2": handle_image_matching2,
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