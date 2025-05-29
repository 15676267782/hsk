import streamlit as st
from util import init_sample_images,show_question_type_example,generate_prompt,get_completion,clean_json_response
from config import QUESTION_TYPES
from handle import QUESTION_HANDLERS



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