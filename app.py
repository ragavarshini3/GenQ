from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
import random

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

app = Flask(__name__)
app.secret_key = "your-secret-key-genai-2026"  # Change this in production

# Question templates for fallback generation
QUESTION_TEMPLATES = {
    "2mark": [
        "Define and explain the concept of {topic}.",
        "What is {topic}? List its key characteristics.",
        "Describe the importance of {topic} in {context}.",
        "Explain the difference between {topic} and related concepts.",
        "What are the main advantages of {topic}?",
        "Write short notes on {topic}.",
        "Differentiate between {topic_a} and {topic_b}.",
        "What do you understand by {topic}?"
    ],
    "5mark": [
        "Explain {topic} in detail with relevant examples.",
        "Discuss the principles and applications of {topic}.",
        "How is {topic} implemented in modern systems? Explain.",
        "Analyze the advantages and disadvantages of {topic}.",
        "Describe the process of {topic} with a flowchart.",
        "Compare and contrast {topic_a} and {topic_b}.",
        "What are the practical applications of {topic}? Discuss.",
        "Explain the architecture/structure of {topic}."
    ],
    "10mark": [
        "Write a comprehensive essay on {topic}. Include examples and diagrams where applicable.",
        "Analyze and discuss the significance of {topic} in detail.",
        "Compare {topic_a} and {topic_b} with their advantages, disadvantages, and real-world applications.",
        "Describe the complete process/lifecycle of {topic} with detailed explanation.",
        "Discuss the challenges and solutions related to {topic}.",
        "Evaluate the impact of {topic} on modern technology.",
        "Explain the theoretical foundations and practical implementations of {topic}.",
        "Create a detailed analysis of {topic} including case studies and examples."
    ]
}

def generate_fallback_questions(course, syllabus, two_marks, five_marks, ten_marks):
    """Generate questions locally when API is unavailable"""
    topics = [t.strip() for t in syllabus.split(',') if t.strip()]
    
    if not topics:
        topics = course.split()
    
    questions = f"Question Paper - {course}\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    questions += f"{'='*60}\n"
    
    # Section A - 2 Mark Questions
    questions += f"SECTION A - 2 Mark Questions ({two_marks} questions)\n"
    questions += f"{'='*60}\n\n"
    for i in range(1, int(two_marks) + 1):
        template = random.choice(QUESTION_TEMPLATES["2mark"])
        topic = random.choice(topics)
        compare_topics = random.sample(topics, 2) if len(topics) >= 2 else [topic, topic]
        question = template.format(
            topic=topic,
            context=course,
            topic_a=compare_topics[0],
            topic_b=compare_topics[1]
        )
        questions += f"{i}. {question}\n\n"
    
    # Section B - 5 Mark Questions
    questions += f"\n{'='*60}\n"
    questions += f"SECTION B - 5 Mark Questions ({five_marks} questions)\n"
    questions += f"{'='*60}\n\n"
    for i in range(1, int(five_marks) + 1):
        template = random.choice(QUESTION_TEMPLATES["5mark"])
        topic = random.choice(topics)
        compare_topics = random.sample(topics, 2) if len(topics) >= 2 else [topic, topic]
        question = template.format(
            topic=topic,
            context=course,
            topic_a=compare_topics[0],
            topic_b=compare_topics[1]
        )
        questions += f"{i}. {question}\n\n"
    
    # Section C - 10 Mark Questions
    questions += f"\n{'='*60}\n"
    questions += f"SECTION C - 10 Mark Questions ({ten_marks} questions)\n"
    questions += f"{'='*60}\n\n"
    for i in range(1, int(ten_marks) + 1):
        template = random.choice(QUESTION_TEMPLATES["10mark"])
        topic = random.choice(topics)
        compare_topics = random.sample(topics, 2) if len(topics) >= 2 else [topic, topic]
        question = template.format(
            topic=topic,
            context=course,
            topic_a=compare_topics[0],
            topic_b=compare_topics[1]
        )
        questions += f"{i}. {question}\n\n"
    
    return questions

# Department and Courses with Syllabus
DEPARTMENTS = {
    "AI&DS": {
        "name": "Artificial Intelligence and Data Science",
        "courses": {
            "Machine Learning": "Supervised Learning, Unsupervised Learning, Regression, Classification, Clustering, Feature Engineering, Model Selection",
            "Deep Learning": "Neural Networks, CNNs, RNNs, LSTMs, GANs, Transfer Learning, Activation Functions",
            "Natural Language Processing": "Tokenization, Word Embeddings, Sentiment Analysis, Named Entity Recognition, Machine Translation",
            "Computer Vision": "Image Processing, Object Detection, Image Segmentation, Face Recognition, Convolutional Networks",
            "Big Data Analytics": "Hadoop, Spark, MapReduce, NoSQL Databases, Data Visualization, Stream Processing",
            "Data Structures and Algorithms": "Arrays, Linked Lists, Trees, Graphs, Sorting, Searching, Dynamic Programming"
        }
    },
    "IT": {
        "name": "Information Technology",
        "courses": {
            "Web Development": "HTML, CSS, JavaScript, React, Angular, Node.js, REST APIs, Web Security",
            "Database Management Systems": "SQL, NoSQL, Normalization, Indexing, Query Optimization, ACID Properties",
            "Software Engineering": "SDLC, Design Patterns, UML, Agile, Version Control, Testing Strategies",
            "Cloud Computing": "AWS, Azure, Google Cloud, Virtualization, Containers, Docker, Kubernetes",
            "Cybersecurity": "Network Security, Cryptography, Penetration Testing, Firewalls, SSL/TLS, Authentication",
            "IT Infrastructure": "Networking, Server Administration, System Design, Load Balancing, Disaster Recovery"
        }
    },
    "ECE": {
        "name": "Electronics and Communication Engineering",
        "courses": {
            "Digital Signal Processing": "Fourier Transform, Filters, Z-Transform, DFT, Signal Analysis, Audio Processing",
            "Microprocessors": "Assembly Language, 8085, 8086, Addressing Modes, Interrupts, Control Signals",
            "Communication Systems": "Modulation, Demodulation, Frequency Spectrum, Bandwidth, Signal-to-Noise Ratio",
            "Embedded Systems": "Microcontrollers, Arduino, Firmware Development, Real-time Systems, IoT Applications",
            "VLSI Design": "Logic Design, Circuit Design, Layout, Simulation, Standard Cells, Physical Design",
            "Wireless Networks": "Wi-Fi, Bluetooth, 4G/5G, Network Protocols, Antenna Design, Spectrum Management"
        }
    },
    "CS": {
        "name": "Computer Science",
        "courses": {
            "Operating Systems": "Process Management, Memory Management, File Systems, Scheduling, Synchronization",
            "Compiler Design": "Lexical Analysis, Syntax Analysis, Code Generation, Optimization, Semantic Analysis",
            "Database Design": "Relational Model, ER Diagrams, Query Languages, Transaction Management, Backup",
            "Network Protocols": "TCP/IP, DNS, HTTP, HTTPS, BGP, OSPF, Network Layers",
            "Artificial Intelligence": "Search Algorithms, Game Theory, Problem Solving, Knowledge Representation",
            "Computer Graphics": "2D/3D Graphics, Ray Tracing, Shading, Animation, Graphics Pipelines"
        }
    }
}

# Department/Course-based quiz bank for students
QUIZ_BANK = {
    "AI&DS": {
        "Machine Learning": [
            {"question": "Which algorithm is commonly used for classification?", "options": ["Linear Regression", "K-Means", "Logistic Regression", "Apriori"], "answer": "Logistic Regression"},
            {"question": "Overfitting means:", "options": ["Model performs poorly on training and test data", "Model performs well on training but poorly on test data", "Model performs poorly only on training data", "Model has too few parameters"], "answer": "Model performs well on training but poorly on test data"},
            {"question": "Which is a supervised learning task?", "options": ["Clustering", "Dimensionality Reduction", "Classification", "Association Rule Mining"], "answer": "Classification"},
            {"question": "What is used to evaluate classification models?", "options": ["Confusion Matrix", "Fourier Transform", "Z-Score", "Min-Max Scaling"], "answer": "Confusion Matrix"},
            {"question": "Feature engineering is primarily used to:", "options": ["Increase internet speed", "Improve model input quality", "Reduce file size only", "Generate random labels"], "answer": "Improve model input quality"}
        ],
        "Deep Learning": [
            {"question": "CNN is primarily used for:", "options": ["Time-series forecasting only", "Image-related tasks", "Sorting data", "Database indexing"], "answer": "Image-related tasks"},
            {"question": "LSTM is designed to handle:", "options": ["Only static images", "Sequential data with long-term dependencies", "Only binary files", "Only SQL queries"], "answer": "Sequential data with long-term dependencies"},
            {"question": "Activation functions are used to:", "options": ["Make model non-linear", "Store data permanently", "Reduce network bandwidth", "Encrypt files"], "answer": "Make model non-linear"},
            {"question": "Transfer learning helps by:", "options": ["Training from scratch always", "Using pre-trained models", "Removing all layers", "Ignoring existing weights"], "answer": "Using pre-trained models"},
            {"question": "GAN consists of:", "options": ["Generator and Discriminator", "Encoder and Decoder only", "Client and Server", "Parser and Compiler"], "answer": "Generator and Discriminator"}
        ],
        "Big Data Analytics": [
            {"question": "Hadoop storage component is:", "options": ["HDFS", "JDBC", "REST", "SMTP"], "answer": "HDFS"},
            {"question": "Spark is known for:", "options": ["In-memory processing", "Only disk-based processing", "Only C programming", "Image editing"], "answer": "In-memory processing"},
            {"question": "MapReduce consists of:", "options": ["Map and Reduce phases", "Read and Write only", "Stack and Queue", "Encode and Decode"], "answer": "Map and Reduce phases"},
            {"question": "Which database type is common in big data?", "options": ["NoSQL", "Only Excel", "Only flat files", "Only XML"], "answer": "NoSQL"},
            {"question": "Stream processing handles:", "options": ["Only archived data", "Real-time data flows", "Only text files", "Only local backups"], "answer": "Real-time data flows"}
        ]
    },
    "IT": {
        "Web Development": [
            {"question": "Which language is used for page structure?", "options": ["CSS", "JavaScript", "HTML", "SQL"], "answer": "HTML"},
            {"question": "CSS is mainly used for:", "options": ["Styling", "Database design", "Version control", "Authentication only"], "answer": "Styling"},
            {"question": "REST APIs commonly use:", "options": ["HTTP methods", "Bluetooth", "Serial ports", "Assembly instructions"], "answer": "HTTP methods"},
            {"question": "Node.js is primarily used for:", "options": ["Server-side JavaScript", "Photo editing", "Spreadsheet formulas", "Hardware debugging"], "answer": "Server-side JavaScript"},
            {"question": "A common frontend framework is:", "options": ["React", "HDFS", "NumPy", "Dockerfile"], "answer": "React"}
        ],
        "Database Management Systems": [
            {"question": "SQL is used for:", "options": ["Querying relational databases", "Image compression", "Packet routing", "Audio recording"], "answer": "Querying relational databases"},
            {"question": "Normalization helps to:", "options": ["Reduce redundancy", "Increase duplicate data", "Slow queries", "Remove indexes"], "answer": "Reduce redundancy"},
            {"question": "ACID stands for:", "options": ["Atomicity, Consistency, Isolation, Durability", "Access, Control, Input, Data", "Array, Class, Interface, Data", "None"], "answer": "Atomicity, Consistency, Isolation, Durability"},
            {"question": "NoSQL is best described as:", "options": ["Non-relational database family", "Only SQL joins", "A markup language", "A UI toolkit"], "answer": "Non-relational database family"},
            {"question": "Indexing is used to:", "options": ["Speed up data retrieval", "Slow down reads", "Delete schema", "Encrypt passwords"], "answer": "Speed up data retrieval"}
        ]
    },
    "ECE": {
        "Digital Signal Processing": [
            {"question": "DFT stands for:", "options": ["Discrete Fourier Transform", "Direct Filter Technique", "Data Flow Transfer", "Digital Frame Timing"], "answer": "Discrete Fourier Transform"},
            {"question": "A low-pass filter allows:", "options": ["Low frequencies", "High frequencies only", "No frequencies", "Random frequencies"], "answer": "Low frequencies"},
            {"question": "Z-transform is used in:", "options": ["Discrete-time signal analysis", "Web styling", "Database indexing", "Cloud billing"], "answer": "Discrete-time signal analysis"},
            {"question": "Sampling theorem is related to:", "options": ["Signal reconstruction", "Compiler optimization", "OS scheduling", "Packet switching"], "answer": "Signal reconstruction"},
            {"question": "Convolution in DSP is used for:", "options": ["System output computation", "Password hashing only", "Image cropping only", "Memory allocation"], "answer": "System output computation"}
        ]
    },
    "CS": {
        "Operating Systems": [
            {"question": "Which scheduling algorithm is non-preemptive?", "options": ["Round Robin", "FCFS", "SRTF", "Priority Preemptive"], "answer": "FCFS"},
            {"question": "A process in OS is:", "options": ["Program in execution", "A text editor", "A network cable", "A hardware chip"], "answer": "Program in execution"},
            {"question": "Deadlock requires how many necessary conditions?", "options": ["2", "3", "4", "5"], "answer": "4"},
            {"question": "Virtual memory helps to:", "options": ["Extend apparent RAM", "Increase monitor size", "Improve keyboard speed", "Remove files"], "answer": "Extend apparent RAM"},
            {"question": "Semaphore is used for:", "options": ["Process synchronization", "Web page rendering", "Data compression", "Disk formatting"], "answer": "Process synchronization"}
        ]
    }
}


def get_default_department(user_department):
    if user_department and user_department in DEPARTMENTS:
        return user_department
    return next(iter(DEPARTMENTS.keys()))


def get_courses_for_department(department):
    return DEPARTMENTS.get(department, {}).get("courses", {})


def get_quiz_questions(department, course, count=5):
    syllabus = DEPARTMENTS.get(department, {}).get("courses", {}).get(course, "")

    if api_key:
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            uniqueness_seed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            prompt = f"""Generate {count} multiple-choice quiz questions.
Department: {DEPARTMENTS.get(department, {}).get('name', department)}
Course: {course}
Syllabus Topics: {syllabus}
Unique Seed: {uniqueness_seed}

Rules:
1. Return ONLY valid JSON array.
2. Each item must have exactly these keys: question, options, answer.
3. options must have exactly 4 distinct strings.
4. answer must exactly match one of the options.
5. Keep questions clear and suitable for undergraduate students.

Output format example:
[
  {{"question": "...", "options": ["A", "B", "C", "D"], "answer": "B"}}
]"""

            response = model.generate_content(prompt)
            raw_text = (response.text or "").strip()

            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()

            start_index = raw_text.find('[')
            end_index = raw_text.rfind(']')
            if start_index != -1 and end_index != -1:
                raw_text = raw_text[start_index:end_index + 1]

            generated = json.loads(raw_text)
            validated_questions = []
            for item in generated:
                question = str(item.get("question", "")).strip()
                options = item.get("options", [])
                answer = str(item.get("answer", "")).strip()

                if question and isinstance(options, list) and len(options) == 4:
                    clean_options = [str(option).strip() for option in options]
                    if answer in clean_options and len(set(clean_options)) == 4:
                        validated_questions.append({
                            "question": question,
                            "options": clean_options,
                            "answer": answer
                        })

            if validated_questions:
                return validated_questions[:count]
        except Exception:
            pass

    course_quiz = QUIZ_BANK.get(department, {}).get(course, [])
    if not course_quiz:
        return []
    if len(course_quiz) <= count:
        return random.sample(course_quiz, len(course_quiz))
    return random.sample(course_quiz, count)

# Simple user database
USERS = {
    "student1": {"password": "student123", "role": "student", "name": "John Student", "department": "AI&DS"},
    "staff1": {"password": "staff123", "role": "staff", "name": "Ms. Smith", "department": "IT"},
    "admin": {"password": "admin123", "role": "staff", "name": "Admin", "department": "CS"}
}

# File to store past papers
PAST_PAPERS_FILE = "past_papers.json"
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return USERS.copy()

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_past_papers():
    if os.path.exists(PAST_PAPERS_FILE):
        with open(PAST_PAPERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_past_papers(papers):
    with open(PAST_PAPERS_FILE, 'w') as f:
        json.dump(papers, f, indent=2)


def is_paper_published_for_students(paper):
    return paper.get("published", True)

@app.route("/")
def home():
    if 'user' in session:
        if session.get('role') == 'staff':
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        users = load_users()
        if username in users and users[username]["password"] == password:
            session['user'] = username
            session['role'] = users[username]['role']
            session['name'] = users[username]['name']
            session['department'] = users[username].get('department', '')
            return redirect(url_for('home'))
        else:
            return render_template("login.html", error="Invalid credentials")
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        name = request.form["name"]
        role = request.form["role"]
        department = request.form["department"]
        
        users = load_users()
        
        if username in users:
            return render_template("register.html", error="Username already exists!", departments=DEPARTMENTS)
        
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match!", departments=DEPARTMENTS)
        
        if len(password) < 6:
            return render_template("register.html", error="Password must be at least 6 characters!", departments=DEPARTMENTS)
        
        # Add new user
        users[username] = {
            "password": password,
            "role": role,
            "name": name,
            "department": department
        }
        save_users(users)
        
        return render_template("register.html", success="Registration successful! Please login.", departments=DEPARTMENTS)
    
    return render_template("register.html", departments=DEPARTMENTS)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/student")
def student_dashboard():
    if 'user' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    users = load_users()
    current_user = users.get(session.get('user'), {})
    user_department = session.get('department') or current_user.get('department', '')

    selected_department = request.args.get('department', '').strip()
    if not selected_department:
        selected_department = get_default_department(user_department)

    courses = get_courses_for_department(selected_department)
    selected_course = request.args.get('course', '').strip()
    if selected_course and selected_course not in courses:
        selected_course = ''

    papers = load_past_papers()
    filtered_papers = [
        paper for paper in papers
        if paper.get('department') == selected_department and is_paper_published_for_students(paper)
    ]
    if selected_course:
        filtered_papers = [paper for paper in filtered_papers if paper.get('course') == selected_course]

    active_quiz = session.get('active_quiz')
    quiz_result = session.pop('quiz_result', None)

    return render_template(
        "student_dashboard.html",
        papers=filtered_papers,
        user=session.get('name'),
        departments=DEPARTMENTS,
        selected_department=selected_department,
        selected_course=selected_course,
        courses=courses,
        active_quiz=active_quiz,
        quiz_result=quiz_result
    )


@app.route("/student/quiz/start", methods=["POST"])
def start_student_quiz():
    if 'user' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    department = request.form.get("department", "").strip()
    course = request.form.get("course", "").strip()

    if department not in DEPARTMENTS:
        return redirect(url_for('student_dashboard'))

    if course not in DEPARTMENTS[department]["courses"]:
        return redirect(url_for('student_dashboard', department=department))

    questions = get_quiz_questions(department, course)
    session['active_quiz'] = {
        "department": department,
        "course": course,
        "questions": questions
    }
    session.pop('quiz_result', None)

    return redirect(url_for('student_dashboard', department=department, course=course))


@app.route("/student/quiz/submit", methods=["POST"])
def submit_student_quiz():
    if 'user' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    active_quiz = session.get('active_quiz')
    if not active_quiz:
        return redirect(url_for('student_dashboard'))

    questions = active_quiz.get("questions", [])
    score = 0
    detailed_result = []

    for index, question_data in enumerate(questions):
        selected_answer = request.form.get(f"q_{index}", "")
        correct_answer = question_data.get("answer", "")
        is_correct = selected_answer == correct_answer
        if is_correct:
            score += 1

        detailed_result.append({
            "question": question_data.get("question", ""),
            "selected": selected_answer or "Not Answered",
            "correct": correct_answer,
            "is_correct": is_correct
        })

    session['quiz_result'] = {
        "score": score,
        "total": len(questions),
        "details": detailed_result,
        "department": active_quiz.get("department", ""),
        "course": active_quiz.get("course", "")
    }
    session.pop('active_quiz', None)

    return redirect(url_for(
        'student_dashboard',
        department=active_quiz.get("department", ""),
        course=active_quiz.get("course", "")
    ))

@app.route("/staff")
def staff_dashboard():
    if 'user' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    user_dept = session.get('department', 'AI&DS')
    papers = load_past_papers()
    staff_papers = [paper for paper in papers if paper.get('department') == user_dept]
    staff_papers.sort(key=lambda item: item.get('id', 0), reverse=True)

    return render_template(
        "staff_dashboard.html",
        user=session.get('name'),
        departments=DEPARTMENTS,
        user_dept=user_dept,
        staff_papers=staff_papers
    )


@app.route("/staff/publish/<int:paper_id>", methods=["POST"])
def publish_paper(paper_id):
    if 'user' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))

    papers = load_past_papers()
    user_dept = session.get('department', 'AI&DS')
    for paper in papers:
        if paper.get('id') == paper_id and paper.get('department') == user_dept:
            paper['published'] = True
            paper['published_by'] = session.get('name')
            paper['published_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_past_papers(papers)
            break

    return redirect(url_for('staff_dashboard'))

@app.route("/generate", methods=["POST"])
def generate():
    if 'user' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))

    department = request.form["department"]
    course = request.form["course"]
    difficulty = request.form["difficulty"]
    two_marks = request.form["two_marks"]
    five_marks = request.form["five_marks"]
    ten_marks = request.form["ten_marks"]
    
    # Get syllabus for the selected course
    syllabus = DEPARTMENTS[department]["courses"].get(course, "")

    prompt = f"""Generate a question paper for the following:
Department: {DEPARTMENTS[department]['name']}
Course: {course}
Syllabus Topics: {syllabus}
Difficulty Level: {difficulty}

Create:
- {two_marks} questions of 2 marks each
- {five_marks} questions of 5 marks each
- {ten_marks} questions of 10 marks each

Format the response clearly with sections A, B, and C."""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        output = response.text
    except Exception as e:
        error_str = str(e)
        # If quota exceeded or API error, use fallback generator
        if "429" in error_str or "quota" in error_str.lower() or "rate_limit" in error_str.lower():
            output = generate_fallback_questions(course, syllabus, two_marks, five_marks, ten_marks)
        else:
            output = f"Error: {str(e)}"

    try:
        papers = load_past_papers()
        paper = {
            "id": len(papers) + 1,
            "department": department,
            "course": course,
            "syllabus": syllabus,
            "difficulty": difficulty,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": output,
            "created_by": session.get('name'),
            "published": False
        }
        papers.append(paper)
        save_past_papers(papers)

        user_dept = session.get('department', 'AI&DS')
        staff_papers = [item for item in papers if item.get('department') == user_dept]
        staff_papers.sort(key=lambda item: item.get('id', 0), reverse=True)
        return render_template(
            "staff_dashboard.html",
            output=output,
            user=session.get('name'),
            success=True,
            departments=DEPARTMENTS,
            user_dept=user_dept,
            paper_id=paper['id'],
            paper_published=paper.get('published', False),
            staff_papers=staff_papers
        )
    except Exception as e:
        user_dept = session.get('department', 'AI&DS')
        papers = load_past_papers()
        staff_papers = [item for item in papers if item.get('department') == user_dept]
        staff_papers.sort(key=lambda item: item.get('id', 0), reverse=True)
        return render_template(
            "staff_dashboard.html",
            output=f"Error: {str(e)}",
            user=session.get('name'),
            departments=DEPARTMENTS,
            user_dept=user_dept,
            staff_papers=staff_papers
        )

def generate_pdf(paper):
    """Generate PDF from question paper"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#00c6ff'),
        spaceAfter=12,
        alignment=1
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#0072ff'),
        spaceAfter=8,
        spaceBefore=8
    )
    
    # Add title
    title = f"{DEPARTMENTS[paper['department']]['name']}<br/>{paper['course']}"
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Add metadata
    meta_data = f"<b>Difficulty:</b> {paper['difficulty']} | <b>Date:</b> {paper['date']} | <b>Created by:</b> {paper['created_by']}"
    elements.append(Paragraph(meta_data, styles['Normal']))
    elements.append(Spacer(1, 0.1*inch))
    
    # Add syllabus
    elements.append(Paragraph("<b>Syllabus Topics:</b>", heading_style))
    elements.append(Paragraph(paper['syllabus'], styles['Normal']))
    elements.append(Spacer(1, 0.15*inch))
    
    # Add content
    elements.append(Paragraph("<b>Question Paper:</b>", heading_style))
    content_lines = paper['content'].split('\n')
    for line in content_lines:
        if line.strip():
            elements.append(Paragraph(line, styles['Normal']))
        else:
            elements.append(Spacer(1, 0.05*inch))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.route("/download_pdf/<int:paper_id>")
def download_pdf(paper_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    papers = load_past_papers()
    for paper in papers:
        if paper['id'] == paper_id:
            if session.get('role') == 'student' and not is_paper_published_for_students(paper):
                return redirect(url_for('student_dashboard'))
            pdf_buffer = generate_pdf(paper)
            filename = f"{paper['course'].replace(' ', '_')}_{paper['id']}.pdf"
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
    
    return redirect(url_for('student_dashboard'))

@app.route("/view_paper/<int:paper_id>")
def view_paper(paper_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    papers = load_past_papers()
    for paper in papers:
        if paper['id'] == paper_id:
            if session.get('role') == 'student' and not is_paper_published_for_students(paper):
                return redirect(url_for('student_dashboard'))
            return render_template("view_paper.html", paper=paper)
    
    return redirect(url_for('student_dashboard'))

if __name__ == "__main__":
    app.run(debug=True)
