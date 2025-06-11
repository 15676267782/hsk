import streamlit as st
from util import init_sample_images, show_question_type_example, generate_prompt, get_completion, clean_json_response
from config import QUESTION_TYPES
from handle import QUESTION_HANDLERS

# 清理缓存
st.cache_data.clear()

# 在 QUESTION_TYPES 字典后添加试卷配置
PAPER_CONFIG = {
    "HSK1": {
        "听力": {
            "听力看图判断题": 1,
            "看图选择题": 1,
            "图片排序题": 1,
            "听录音选择题": 1,
        },
        "阅读": {
            "阅读看图判断题": 1,
            "图片匹配题": 1,
            "问答匹配题": 1,
            "选词填空题": 1
        }
    },
    "HSK2": {
        "听力": {
            "听力看图判断题": 1,
            "听对话选择题": 1,
            "图片排序题": 1,
        },
        "阅读": {
            "选词填空题": 1,
            "句子匹配题": 1,
            "阅读判断题": 1,
            "图片匹配题2": 1,
        }
    },
    "HSK3": {
        "听力": {
            "图片排序题": 1,
            "听对话选择题": 1,
            "文字判断题": 1,
        },
        "阅读": {
            "选词填空题": 1,
            "句子匹配题": 1,
            "阅读理解题": 1
        }
    },
    "HSK4": {
        "听力": {
            "听对话选择题4": 1,
            "文字判断题": 1,
            "听对话选择题1v2": 1
        },
        "阅读": {
            "阅读理解题": 1,
            "选词填空题": 1,
            "句子排序题": 1,
            "阅读理解题1v2": 1
        }
    },
    "HSK5": {
        "听力": {
            "听对话选择题5": 1,
            "听对话选择题1v3": 1
        },
        "阅读": {
            "短文选词填空题5": 1,
            "阅读文章选择题": 1,
            "长文本理解题": 1
        }
    },
    "HSK6": {
        "听力": {
            "听短文选择题": 1,
            "听对话选择题1v5": 1,
            "听对话选择题6": 1
        },
        "阅读": {
            "短文选词填空题6": 1,
            "病句选择题": 1,
            "短文选句填空题": 1,
            "文章选择题": 1
        }
    }
}


def main():
    # 初始化会话状态（确保每次启动时重置）
    if 'temp_files' not in st.session_state:
        st.session_state.temp_files = []
    if 'generated_papers' not in st.session_state:
        st.session_state.generated_papers = 0
    if 'show_question_generator' not in st.session_state:
        st.session_state.show_question_generator = True
    if 'show_paper_generator' not in st.session_state:
        st.session_state.show_paper_generator = False
    if 'expanded_section' not in st.session_state:
        st.session_state.expanded_section = "question"
    if 'paper_generation_in_progress' not in st.session_state:
        st.session_state.paper_generation_in_progress = False

    # 确保这些变量也存在于 session_state 中，以便在不同模式下访问
    if 'selected_types' not in st.session_state:
        st.session_state.selected_types = []
    if 'num_questions' not in st.session_state:
        st.session_state.num_questions = 5  # 默认值
    if 'paper_type_counts' not in st.session_state:
        st.session_state.paper_type_counts = {}

    st.set_page_config(layout="wide")
    st.title("📚 HSK智能题库生成系统")
    init_sample_images()

    # ===== 左侧控制面板 =====
    with st.sidebar:
        st.header("⚙️ 题目设置")

        # 折叠按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📝 题目生成", type="primary" if st.session_state.expanded_section == "question" else "secondary",
                         key="toggle_question_generator"):
                st.session_state.expanded_section = "question"
                st.session_state.show_question_generator = True
                st.session_state.show_paper_generator = False

        with col2:
            if st.button("📄 试卷生成", type="primary" if st.session_state.expanded_section == "paper" else "secondary",
                         key="toggle_paper_generator"):
                st.session_state.expanded_section = "paper"
                st.session_state.show_question_generator = False
                st.session_state.show_paper_generator = True

        # 1. 选择HSK级别（两个模式共用）
        level = st.selectbox(
            "选择HSK级别",
            list(QUESTION_TYPES.keys()),
            index=0,  # 默认HSK1
            key="hsk_level_selector"
        )

        # 2. 选择题型分类（两个模式共用）
        category = st.selectbox(
            "选择题型分类",
            list(QUESTION_TYPES[level].keys()),
            key="category_selector"
        )

        # 题目生成区域
        if st.session_state.show_question_generator:
            st.markdown("---")
            st.markdown("### 题目生成设置")

            # 3. 选择具体题型（多选）
            st.markdown("**选择具体题型：**")
            st.session_state.selected_types = []  # 每次显示时清空，重新收集
            type_counts = {}  # 存储每种题型的数量

            for type_name in QUESTION_TYPES[level][category]:
                cols = st.columns([1, 3, 1])
                with cols[0]:
                    # 检查 st.session_state[f"check_{type_name}"] 是否存在，如果不存在则初始化为 False
                    if f"check_{type_name}" not in st.session_state:
                        st.session_state[f"check_{type_name}"] = False

                    if st.checkbox("", key=f"check_{type_name}", value=st.session_state[f"check_{type_name}"]):
                        st.session_state.selected_types.append(type_name)
                with cols[1]:
                    show_question_type_example(level, category, type_name)
                with cols[2]:
                    # 为选中的题型添加数量选择器
                    if f"check_{type_name}" in st.session_state and st.session_state[f"check_{type_name}"]:
                        count = st.number_input(
                            "",
                            min_value=1,
                            max_value=10,
                            value=PAPER_CONFIG.get(level, {}).get(category, {}).get(type_name, 5),
                            key=f"count_{type_name}"
                        )
                        type_counts[type_name] = count

            # 将 type_counts 存储到 session_state，以便在生成题目时使用
            st.session_state.question_type_counts = type_counts

            # 4. 题目数量控制
            st.session_state.num_questions = st.slider(  # 直接更新 session_state
                "题目数量",
                min_value=1,
                max_value=20,
                value=st.session_state.num_questions,  # 使用 session_state 中的值
                help="每组生成的题目数量",
                key="question_count_slider"
            )

            # 5. 高级选项（HSK5-6）
            if level in ["HSK5", "HSK6"]:
                st.markdown("**高级设置：**")
                st.checkbox("使用高级词汇", True, key="advanced_vocab_checkbox")
                st.checkbox("包含文化知识点", False, key="culture_checkbox")

        # 试卷生成区域
        if st.session_state.show_paper_generator:
            st.markdown("---")
            st.markdown("### 试卷生成设置")

            generate_full_paper = st.checkbox("生成完整试卷", True, key="generate_full_paper")

            if generate_full_paper:
                st.markdown("### 自定义题型数量")
                # 初始化 paper_type_counts
                if 'paper_type_counts' not in st.session_state:
                    st.session_state.paper_type_counts = {}

                # 获取该级别的试卷配置
                level_config = PAPER_CONFIG.get(level, {})

                # 为每个分类和题型创建数量选择器
                for cat, types_in_cat in level_config.items():
                    st.markdown(f"#### {cat}")
                    if cat not in st.session_state.paper_type_counts:
                        st.session_state.paper_type_counts[cat] = {}

                    for type_name, default_count in types_in_cat.items():
                        cols = st.columns([3, 1])
                        with cols[0]:
                            st.text(type_name)
                        with cols[1]:
                            count = st.number_input(
                                "",
                                min_value=0,
                                max_value=20,
                                value=st.session_state.paper_type_counts.get(cat, {}).get(type_name, default_count),
                                # 使用 session_state 中的值或默认值
                                key=f"paper_count_{cat}_{type_name}"
                            )
                            st.session_state.paper_type_counts[cat][type_name] = count  # 更新 session_state

    # ===== 主内容区域 =====
    with st.container():
        # 一键生成试卷按钮
        if st.button("📝 一键生成试卷", type="primary",
                     key="generate_paper_button") and not st.session_state.paper_generation_in_progress:
            # 设置生成中标志，防止重复点击
            st.session_state.paper_generation_in_progress = True

            # 每次点击前重置生成计数
            st.session_state.generated_papers = 0

            with st.spinner(f"正在生成{level}试卷..."):
                all_questions = []

                # 从 session_state 中获取自定义数量
                current_paper_type_counts = st.session_state.paper_type_counts

                # 检查是否使用自定义数量
                if generate_full_paper and current_paper_type_counts:  # 确保 generate_full_paper 为 True 且 paper_type_counts 不为空
                    # 使用用户在侧边栏配置的数量
                    for cat, types_in_cat in current_paper_type_counts.items():
                        for type_name, count in types_in_cat.items():
                            if count <= 0:
                                continue

                            prompt = generate_prompt(level, cat, [type_name], count)  # 使用循环中的 cat
                            response = get_completion(prompt)

                            if response:
                                data = clean_json_response(response)
                                if data and "questions" in data:
                                    for q in data["questions"]:
                                        q["category"] = cat  # 确保题目包含正确的分类信息
                                    all_questions.extend(data["questions"])
                else:
                    # 使用默认配置
                    paper_config = PAPER_CONFIG.get(level, {})
                    for cat, types_in_cat in paper_config.items():
                        for type_name, count in types_in_cat.items():
                            prompt = generate_prompt(level, cat, [type_name], count)  # 使用循环中的 cat
                            response = get_completion(prompt)

                            if response:
                                data = clean_json_response(response)
                                if data and "questions" in data:
                                    for q in data["questions"]:
                                        q["category"] = cat  # 确保题目包含正确的分类信息
                                    all_questions.extend(data["questions"])

                # 保存到会话状态（确保只保存一套试卷）
                if all_questions:
                    st.session_state.questions = all_questions
                    st.session_state.level = level
                    st.session_state.category = "试卷"
                    st.session_state.generated_papers = 1  # 标记已生成一套
                    display_questions(all_questions, level, "试卷")
                else:
                    st.error("生成试卷失败，请重试")

                # 重置生成中标志
                st.session_state.paper_generation_in_progress = False

        st.markdown("---")  # 添加分隔线，用于视觉区分

        # 原有的生成题目按钮
        if st.button("🚀 生成题目", type="primary", key="generate_questions_button"):
            # 从 session_state 中获取最新的 selected_types 和 num_questions
            current_selected_types = st.session_state.selected_types
            current_num_questions = st.session_state.num_questions

            if not current_selected_types:  # 将此检查移到按钮点击逻辑内部
                st.warning("请至少选择一种题型")
            else:
                with st.spinner(f"正在生成{level} {category}题目..."):
                    # 1. 生成Prompt
                    prompt = generate_prompt(level, category, current_selected_types, current_num_questions)

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


def display_questions(questions, level, category):
    """展示生成的题目，根据题型分发到不同的处理器"""

    # 添加试卷标题
    if category == "试卷":
        st.title(f"📚 {level} 模拟试卷")
        st.markdown("---")

    for i, q in enumerate(questions, 1):
        with st.container():
            # 题型标题
            st.subheader(f"题目{i} | {q.get('type', '未知题型')}")

            # 对于试卷模式，使用题目中的分类信息
            actual_category = q.get("category", category)

            # 根据题型选择对应的处理器
            question_type = q.get('type', '')
            handler = QUESTION_HANDLERS.get(question_type)

            if handler:
                # 调用对应的处理器，使用正确的分类信息
                handler(q, level, actual_category, i)
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
