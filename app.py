# -*- coding: utf-8 -*-
import streamlit as st
import os
import json
import time
from util import (
    generate_questions, save_questions, load_questions, list_saved_questions,
    get_examples, get_hsk_level, adjust_text_by_hsk
)
from handle import (
    handle_look_and_judge1, handle_look_and_choice, handle_image_sorting,
    handle_listening, handle_text_judgment1, handle_audio_dialogue_questions,
    handle_article_listening
)
from config import DETAILED_QUESTION_CONFIG

# 设置页面配置
st.set_page_config(
    page_title="HSK题目生成器",
    page_icon="📚",
    layout="wide"
)

# 初始化session state
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'current_question_index' not in st.session_state:
    st.session_state.current_question_index = 0
if 'temp_files' not in st.session_state:
    st.session_state.temp_files = []

# 标题
st.title("HSK题目生成器 📚")

# 侧边栏配置
st.sidebar.markdown("### 配置选项")

# HSK等级选择
level = st.sidebar.selectbox(
    "选择HSK等级",
    ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"],
    index=3  # 默认选择HSK4
)

# 题目类型选择
category = st.sidebar.selectbox(
    "选择题目类型",
    ["听力", "阅读"],
    index=0  # 默认选择听力
)

# 根据选择的类别显示具体的题目类型
if category == "听力":
    question_type = st.sidebar.selectbox(
        "选择具体题型",
        ["听对话选择题1v2", "听对话选择题1v3", "听对话选择题1v5", "听录音选择题", "听短文选择题"],
        index=0
    )
else:  # 阅读
    question_type = st.sidebar.selectbox(
        "选择具体题型",
        ["阅读看图判断题", "图片匹配题"],
        index=0
    )

# 题目数量选择
num_questions = st.sidebar.number_input(
    "生成题目数量",
    min_value=1,
    max_value=10,
    value=1
)

# 生成题目按钮
if st.button("生成题目", key="generate"):
    with st.spinner("正在生成题目..."):
        questions = generate_questions(level, category, question_type, num_questions)
        if questions:
            st.session_state.questions = questions
            st.session_state.current_question_index = 0

            # 添加保存按钮
            if st.button("保存题目", key="save_questions"):
                filename = save_questions(questions)
                if filename:
                    st.success(f"题目已保存到: {filename}")

# 加载历史题目功能
st.sidebar.markdown("---")
st.sidebar.markdown("### 加载历史题目")
saved_files = list_saved_questions()
if saved_files:
    selected_file = st.sidebar.selectbox(
        "选择要加载的题目文件",
        saved_files,
        format_func=lambda
            x: f"{x} ({time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(x.split('_')[1].split('.')[0], '%Y%m%d_%H%M%S'))})"
    )

    if st.sidebar.button("加载选中的题目"):
        questions = load_questions(selected_file)
        if questions:
            st.session_state.questions = questions
            st.session_state.current_question_index = 0
            st.success(f"已加载题目文件: {selected_file}")
            st.experimental_rerun()

# 显示题目
if st.session_state.questions:
    # 显示当前题目索引
    st.markdown(f"### 题目 {st.session_state.current_question_index + 1}/{len(st.session_state.questions)}")

    # 获取当前题目
    current_question = st.session_state.questions[st.session_state.current_question_index]

    # 根据题目类型调用相应的处理函数
    if question_type == "听对话选择题1v2":
        handle_audio_dialogue_questions(current_question, level, category, st.session_state.current_question_index)
    elif question_type == "听对话选择题1v3":
        handle_audio_dialogue_questions(current_question, level, category, st.session_state.current_question_index)
    elif question_type == "听对话选择题1v5":
        handle_audio_dialogue_questions(current_question, level, category, st.session_state.current_question_index)
    elif question_type == "听录音选择题":
        handle_listening(current_question, level, category, st.session_state.current_question_index)
    elif question_type == "听短文选择题":
        handle_article_listening(current_question, level, category, st.session_state.current_question_index)
    elif question_type == "阅读看图判断题":
        handle_look_and_judge1(current_question, level, category, st.session_state.current_question_index)
    elif question_type == "图片匹配题":
        handle_image_sorting(current_question, level, category, st.session_state.current_question_index)

    # 添加导航按钮
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.session_state.current_question_index > 0:
            if st.button("上一题"):
                st.session_state.current_question_index -= 1
                st.experimental_rerun()

    with col2:
        st.markdown(
            f"<div style='text-align: center'>第 {st.session_state.current_question_index + 1} 题 / 共 {len(st.session_state.questions)} 题</div>",
            unsafe_allow_html=True)

    with col3:
        if st.session_state.current_question_index < len(st.session_state.questions) - 1:
            if st.button("下一题"):
                st.session_state.current_question_index += 1
                st.experimental_rerun()

# 清理临时文件
if st.session_state.temp_files:
    for file in st.session_state.temp_files:
        if os.path.exists(file):
            try:
                os.remove(file)
            except Exception as e:
                st.warning(f"无法删除临时文件 {file}: {str(e)}")
    st.session_state.temp_files = []