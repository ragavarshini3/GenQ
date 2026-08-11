from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
from datetime import datetime
import time
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
import random

load_dotenv()

# Auto-upgrade requirements.txt permissions and contents
try:
    import stat
    req_path = "requirements.txt"
    if os.path.exists(req_path):
        os.chmod(req_path, stat.S_IWRITE)
        with open(req_path, "w") as f:
            f.write("Flask==2.3.3\npython-dotenv==1.0.0\ngoogle-generativeai>=0.8.3\nreportlab==4.0.7\ngunicorn\n")
except Exception:
    pass

# Clean up any previously saved papers containing error messages
try:
    past_papers_path = "past_papers.json"
    if os.path.exists(past_papers_path):
        with open(past_papers_path, "r") as f:
            papers = json.load(f)
        cleaned_papers = [p for p in papers if not (isinstance(p.get("content"), str) and p["content"].startswith("Error:"))]
        for i, p in enumerate(cleaned_papers):
            p["id"] = i + 1
        with open(past_papers_path, "w") as f:
            json.dump(cleaned_papers, f, indent=2)
except Exception:
    pass

api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    try:
        models = [m.name for m in genai.list_models()]
        with open("available_models.txt", "w") as f:
            f.write("\n".join(models))
    except Exception as e:
        with open("available_models.txt", "w") as f:
            f.write(f"Error: {str(e)}")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key_1234567890_abc")

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
        "Natural Language Processing": [
            {"question": "What is tokenization in NLP?", "options": ["Splitting text into words or sentences", "Converting text to uppercase", "Translating text to another language", "Encrypting text files"], "answer": "Splitting text into words or sentences"},
            {"question": "Which of the following is a common word embedding technique?", "options": ["TF-IDF", "Word2Vec", "Regex", "Lemmatization"], "answer": "Word2Vec"},
            {"question": "What does Named Entity Recognition (NER) identify?", "options": ["Grammatical errors", "Proper nouns like names, locations, and organizations", "The sentiment score of a sentence", "The frequency of words"], "answer": "Proper nouns like names, locations, and organizations"},
            {"question": "What is stemming in text preprocessing?", "options": ["Reducing words to their base or root form", "Adding prefixes to words", "Translating words to another language", "Removing punctuation"], "answer": "Reducing words to their base or root form"},
            {"question": "Which model architecture is the foundation for modern LLMs like GPT?", "options": ["Recurrent Neural Networks", "Convolutional Neural Networks", "Transformer", "Support Vector Machines"], "answer": "Transformer"}
        ],
        "Computer Vision": [
            {"question": "Which neural network architecture is most commonly used for image classification?", "options": ["Recurrent Neural Network (RNN)", "Convolutional Neural Network (CNN)", "Generative Adversarial Network (GAN)", "Feedforward Neural Network"], "answer": "Convolutional Neural Network (CNN)"},
            {"question": "What is the purpose of image segmentation?", "options": ["Classifying the entire image", "Partitioning an image into multiple segments or pixels", "Reducing the resolution of an image", "Converting RGB to Grayscale"], "answer": "Partitioning an image into multiple segments or pixels"},
            {"question": "Which filter is commonly used for edge detection in images?", "options": ["Sobel filter", "Gaussian blur", "Median filter", "Bilinear filter"], "answer": "Sobel filter"},
            {"question": "What does IoU stand for in object detection evaluation?", "options": ["Input over Output", "Index of Uniqueness", "Intersection over Union", "Interface of User"], "answer": "Intersection over Union"},
            {"question": "What is the function of max-pooling in a CNN?", "options": ["Downsamples the input representation to reduce dimensionality", "Increases the number of channels", "Applies activation function", "Performs matrix multiplication"], "answer": "Downsamples the input representation to reduce dimensionality"}
        ],
        "Big Data Analytics": [
            {"question": "Hadoop storage component is:", "options": ["HDFS", "JDBC", "REST", "SMTP"], "answer": "HDFS"},
            {"question": "Spark is known for:", "options": ["In-memory processing", "Only disk-based processing", "Only C programming", "Image editing"], "answer": "In-memory processing"},
            {"question": "MapReduce consists of:", "options": ["Map and Reduce phases", "Read and Write only", "Stack and Queue", "Encode and Decode"], "answer": "Map and Reduce phases"},
            {"question": "Which database type is common in big data?", "options": ["NoSQL", "Only Excel", "Only flat files", "Only XML"], "answer": "NoSQL"},
            {"question": "Stream processing handles:", "options": ["Only archived data", "Real-time data flows", "Only text files", "Only local backups"], "answer": "Real-time data flows"}
        ],
        "Data Structures and Algorithms": [
            {"question": "What is the time complexity of searching in a balanced Binary Search Tree (BST)?", "options": ["O(1)", "O(n)", "O(log n)", "O(n log n)"], "answer": "O(log n)"},
            {"question": "Which data structure operates on a Last In First Out (LIFO) basis?", "options": ["Queue", "Stack", "Linked List", "Heap"], "answer": "Stack"},
            {"question": "Which sorting algorithm has a worst-case time complexity of O(n^2)?", "options": ["Merge Sort", "Quick Sort", "Heap Sort", "Counting Sort"], "answer": "Quick Sort"},
            {"question": "What is a major advantage of a Linked List over an Array?", "options": ["Dynamic size and ease of insertion/deletion", "Random access of elements", "Lower memory overhead", "Cache friendliness"], "answer": "Dynamic size and ease of insertion/deletion"},
            {"question": "Which algorithm is used to find the shortest path in a weighted graph with non-negative edge weights?", "options": ["Dijkstra's Algorithm", "Kruskal's Algorithm", "Prim's Algorithm", "Depth First Search"], "answer": "Dijkstra's Algorithm"}
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
        ],
        "Software Engineering": [
            {"question": "What does SDLC stand for?", "options": ["Software Development Life Cycle", "System Design Logic Cycle", "Structured Data Language Compiler", "Secure Development Line Connection"], "answer": "Software Development Life Cycle"},
            {"question": "Which design pattern ensures a class has only one instance and provides a global point of access to it?", "options": ["Factory Pattern", "Observer Pattern", "Singleton Pattern", "Strategy Pattern"], "answer": "Singleton Pattern"},
            {"question": "What is the primary focus of Agile development methodology?", "options": ["Strict linear phase completion", "Iterative development and customer collaboration", "Detailed documentation upfront", "Eliminating all testing phases"], "answer": "Iterative development and customer collaboration"},
            {"question": "Which type of testing is performed to check if new code changes haven't adversely affected existing features?", "options": ["Unit Testing", "Integration Testing", "Regression Testing", "Acceptance Testing"], "answer": "Regression Testing"},
            {"question": "What is Git?", "options": ["A programming language", "A relational database management system", "A distributed version control system", "A cloud hosting provider"], "answer": "A distributed version control system"}
        ],
        "Cloud Computing": [
            {"question": "Which service model does AWS EC2 belong to?", "options": ["SaaS (Software as a Service)", "PaaS (Platform as a Service)", "IaaS (Infrastructure as a Service)", "FaaS (Function as a Service)"], "answer": "IaaS (Infrastructure as a Service)"},
            {"question": "What is virtualization in cloud computing?", "options": ["Creating physical copies of servers", "Creating virtual versions of physical hardware resources", "Developing virtual reality games", "Encrypting database backups"], "answer": "Creating virtual versions of physical hardware resources"},
            {"question": "What is Docker primarily used for?", "options": ["Compiling C++ code", "Containerizing applications and their dependencies", "Managing cloud billing", "Creating responsive web designs"], "answer": "Containerizing applications and their dependencies"},
            {"question": "Which tool is commonly used to orchestrate and manage containerized applications?", "options": ["Kubernetes", "Git", "MySQL", "Visual Studio Code"], "answer": "Kubernetes"},
            {"question": "What is serverless computing?", "options": ["Computing without using any servers at all", "Developers running code without managing server infrastructure", "Hosting websites on local desktop PCs", "Using database files instead of databases"], "answer": "Developers running code without managing server infrastructure"}
        ],
        "Cybersecurity": [
            {"question": "What is the primary goal of cryptography?", "options": ["Speeding up network connections", "Securing information from unauthorized access", "Formatting code automatically", "Detecting system hardware errors"], "answer": "Securing information from unauthorized access"},
            {"question": "Which protocol provides secure, encrypted communication over the web?", "options": ["HTTP", "HTTPS", "FTP", "SMTP"], "answer": "HTTPS"},
            {"question": "What is a firewall used for?", "options": ["Cooling down server rooms", "Monitoring and filtering incoming/outgoing network traffic", "Speeding up database queries", "Compiling software code"], "answer": "Monitoring and filtering incoming/outgoing network traffic"},
            {"question": "What is SQL injection?", "options": ["A method to speed up SQL database queries", "A vulnerability where malicious SQL statements are injected into inputs", "A process of database normalization", "A technique for backing up data"], "answer": "A vulnerability where malicious SQL statements are injected into inputs"},
            {"question": "What does two-factor authentication (2FA) require?", "options": ["Two different passwords", "Password and an independent secondary verification factor", "Two user accounts", "A security guard and a password"], "answer": "Password and an independent secondary verification factor"}
        ],
        "IT Infrastructure": [
            {"question": "Which device operates at the Network Layer (Layer 3) of the OSI model?", "options": ["Hub", "Switch", "Router", "Repeater"], "answer": "Router"},
            {"question": "What is the purpose of load balancing?", "options": ["Distributing network traffic across multiple servers", "Increasing server processor speed", "Balancing backup power units", "Formatting database hard drives"], "answer": "Distributing network traffic across multiple servers"},
            {"question": "What does DNS stand for?", "options": ["Data Network System", "Domain Name System", "Dynamic Node Server", "Distributed Network Service"], "answer": "Domain Name System"},
            {"question": "What is a major goal of Disaster Recovery (DR) planning?", "options": ["Reducing software license costs", "Minimizing downtime and data loss during a disruptive event", "Optimizing UI colors", "Speeding up local compilation"], "answer": "Minimizing downtime and data loss during a disruptive event"},
            {"question": "Which IP address is commonly used as localhost (loopback address)?", "options": ["192.168.1.1", "127.0.0.1", "10.0.0.1", "8.8.8.8"], "answer": "127.0.0.1"}
        ]
    },
    "ECE": {
        "Digital Signal Processing": [
            {"question": "DFT stands for:", "options": ["Discrete Fourier Transform", "Direct Filter Technique", "Data Flow Transfer", "Digital Frame Timing"], "answer": "Discrete Fourier Transform"},
            {"question": "A low-pass filter allows:", "options": ["Low frequencies", "High frequencies only", "No frequencies", "Random frequencies"], "answer": "Low frequencies"},
            {"question": "Z-transform is used in:", "options": ["Discrete-time signal analysis", "Web styling", "Database indexing", "Cloud billing"], "answer": "Discrete-time signal analysis"},
            {"question": "Sampling theorem is related to:", "options": ["Signal reconstruction", "Compiler optimization", "OS scheduling", "Packet switching"], "answer": "Signal reconstruction"},
            {"question": "Convolution in DSP is used for:", "options": ["System output computation", "Password hashing only", "Image cropping only", "Memory allocation"], "answer": "System output computation"}
        ],
        "Microprocessors": [
            {"question": "What is the size of the data bus in the 8085 microprocessor?", "options": ["4-bit", "8-bit", "16-bit", "32-bit"], "answer": "8-bit"},
            {"question": "Which flag in 8086 is set to 1 when the result of an arithmetic operation is zero?", "options": ["Carry Flag", "Sign Flag", "Zero Flag", "Parity Flag"], "answer": "Zero Flag"},
            {"question": "What does an interrupt do in a microprocessor?", "options": ["Shuts down the processor completely", "Temporarily suspends execution to handle an external event", "Increases the clock frequency", "Deletes the register contents"], "answer": "Temporarily suspends execution to handle an external event"},
            {"question": "Which register is used as a default accumulator in 8086?", "options": ["AX", "BX", "CX", "DX"], "answer": "AX"},
            {"question": "What is the purpose of addressing modes in assembly language?", "options": ["Specifying the way operands are accessed by instructions", "Locating the user's home address", "Determining the internet IP address", "Formatting printer output"], "answer": "Specifying the way operands are accessed by instructions"}
        ],
        "Communication Systems": [
            {"question": "Which modulation technique varies the frequency of the carrier signal?", "options": ["Amplitude Modulation (AM)", "Frequency Modulation (FM)", "Phase Modulation (PM)", "Pulse Code Modulation (PCM)"], "answer": "Frequency Modulation (FM)"},
            {"question": "What does SNR stand for in communication?", "options": ["Signal-to-Noise Ratio", "System Network Router", "Single Node Receiver", "Spectrum Noise Range"], "answer": "Signal-to-Noise Ratio"},
            {"question": "What is Nyquist rate?", "options": ["The maximum speed of a processor", "Minimum sampling rate required to avoid aliasing", "The transmission rate of optical fibers", "The frequency of a carrier wave"], "answer": "Minimum sampling rate required to avoid aliasing"},
            {"question": "Which frequency range is classified as Ultra High Frequency (UHF)?", "options": ["30 to 300 MHz", "300 MHz to 3 GHz", "3 to 30 GHz", "30 to 300 kHz"], "answer": "300 MHz to 3 GHz"},
            {"question": "What is the purpose of demodulation?", "options": ["Combining multiple signals into one", "Extracting original information from a modulated carrier wave", "Increasing signal transmission power", "Filtering out all high frequencies"], "answer": "Extracting original information from a modulated carrier wave"}
        ],
        "Embedded Systems": [
            {"question": "What distinguishes a microcontroller from a microprocessor?", "options": ["Microcontrollers have integrated CPU, memory, and I/O on a single chip", "Microprocessors are only used in analog circuits", "Microcontrollers do not have an ALU", "Microprocessors do not require a clock source"], "answer": "Microcontrollers have integrated CPU, memory, and I/O on a single chip"},
            {"question": "What is a Real-Time Operating System (RTOS)?", "options": ["An OS designed to serve real-time applications with precise timing constraints", "An OS that updates its UI in real-time", "An OS used only in high-end gaming consoles", "An OS that runs on social media websites"], "answer": "An OS designed to serve real-time applications with precise timing constraints"},
            {"question": "Which protocol is a widely used serial communication standard in embedded systems?", "options": ["HTML", "I2C", "FTP", "DNS"], "answer": "I2C"},
            {"question": "What is the function of a Watchdog Timer in embedded systems?", "options": ["Displaying current time to the user", "Resetting the system if the software hangs or freezes", "Measuring external temperature", "Controlling the speed of cooling fans"], "answer": "Resetting the system if the software hangs or freezes"},
            {"question": "What is firmware?", "options": ["Softwares that can be modified by users easily", "Permanent software programmed into a read-only memory of hardware", "Softwares used only for virtual reality", "A type of web framework"], "answer": "Permanent software programmed into a read-only memory of hardware"}
        ],
        "VLSI Design": [
            {"question": "What does VLSI stand for?", "options": ["Very Large Scale Integration", "Virtual Logic System Interface", "Variable Line Segment Indicator", "Volume Level Signal Input"], "answer": "Very Large Scale Integration"},
            {"question": "Which technology is most widely used in modern VLSI design for low power consumption?", "options": ["Bipolar Junction Transistors (BJT)", "Complementary Metal-Oxide-Semiconductor (CMOS)", "Vacuum Tubes", "Resistor-Transistor Logic (RTL)"], "answer": "Complementary Metal-Oxide-Semiconductor (CMOS)"},
            {"question": "What is the primary purpose of synthesis in a VLSI design flow?", "options": ["Converting HDL description into a gate-level netlist", "Testing the physical chip packaging", "Drawing the schematic manually", "Simulating thermal properties of the chip"], "answer": "Converting HDL description into a gate-level netlist"},
            {"question": "Which language is commonly used for hardware description in VLSI?", "options": ["Verilog", "Python", "SQL", "JavaScript"], "answer": "Verilog"},
            {"question": "What is physical design in VLSI?", "options": ["Drawing cartoons of transistors", "Converting gate-level netlist into physical layout on silicon", "Coding the compiler software", "Designing the system casing"], "answer": "Converting gate-level netlist into physical layout on silicon"}
        ],
        "Wireless Networks": [
            {"question": "Which IEEE standard defines wireless local area networks (Wi-Fi)?", "options": ["IEEE 802.3", "IEEE 802.11", "IEEE 802.15", "IEEE 802.1"], "answer": "IEEE 802.11"},
            {"question": "What is the main advantage of 5G networks over 4G?", "options": ["Lower data rates", "Higher latency", "Higher data rates and lower latency", "Lower frequency range"], "answer": "Higher data rates and lower latency"},
            {"question": "What is handoff (or handover) in cellular networks?", "options": ["Turning off a mobile device", "Transferring an active call or data session from one cell site to another", "Buying a new phone from a store", "Sending a text message"], "answer": "Transferring an active call or data session from one cell site to another"},
            {"question": "Which wireless technology is designed for low-power, short-range personal area networks?", "options": ["Wi-Fi", "4G LTE", "Bluetooth", "Satellite communication"], "answer": "Bluetooth"},
            {"question": "What does SSID stand for in wireless networking?", "options": ["Service Set Identifier", "Secure System ID", "Signal Strength Indicator Device", "Serial Signal Input Driver"], "answer": "Service Set Identifier"}
        ]
    },
    "CS": {
        "Operating Systems": [
            {"question": "Which scheduling algorithm is non-preemptive?", "options": ["Round Robin", "FCFS", "SRTF", "Priority Preemptive"], "answer": "FCFS"},
            {"question": "A process in OS is:", "options": ["Program in execution", "A text editor", "A network cable", "A hardware chip"], "answer": "Program in execution"},
            {"question": "Deadlock requires how many necessary conditions?", "options": ["2", "3", "4", "5"], "answer": "4"},
            {"question": "Virtual memory helps to:", "options": ["Extend apparent RAM", "Increase monitor size", "Improve keyboard speed", "Remove files"], "answer": "Extend apparent RAM"},
            {"question": "Semaphore is used for:", "options": ["Process synchronization", "Web page rendering", "Data compression", "Disk formatting"], "answer": "Process synchronization"}
        ],
        "Compiler Design": [
            {"question": "Which phase of a compiler performs syntactic analysis?", "options": ["Lexical Analyzer", "Syntax Analyzer (Parser)", "Code Optimizer", "Code Generator"], "answer": "Syntax Analyzer (Parser)"},
            {"question": "What is the output of the Lexical Analysis phase?", "options": ["Syntax Tree", "Intermediate Code", "Tokens", "Machine Code"], "answer": "Tokens"},
            {"question": "What does a parser use to guide the parsing process?", "options": ["Regular Expressions only", "Context-Free Grammar", "Assembler Directives", "SQL Queries"], "answer": "Context-Free Grammar"},
            {"question": "What is the purpose of intermediate code generation in compilers?", "options": ["Translating directly to binary machine code", "Facilitating machine-independent code optimization", "Validating variable name spellings", "Linking external library files"], "answer": "Facilitating machine-independent code optimization"},
            {"question": "Which data structure is used by compilers to store information about variables, functions, and classes?", "options": ["Stack", "Queue", "Symbol Table", "Linked List"], "answer": "Symbol Table"}
        ],
        "Database Design": [
            {"question": "What does an Entity-Relationship (ER) diagram represent?", "options": ["Computer processor components", "Logical structure of a database", "Flow of internet packets", "User interface design layout"], "answer": "Logical structure of a database"},
            {"question": "Which normal form deals with removing transitive dependencies?", "options": ["1NF", "2NF", "3NF", "BCNF"], "answer": "3NF"},
            {"question": "What is a primary key?", "options": ["A key that allows duplicate values", "A key that uniquely identifies each record in a table", "An encryption key", "A password to access the database server"], "answer": "A key that uniquely identifies each record in a table"},
            {"question": "Which constraint ensures that a value in a column matches a value in another table's primary key column?", "options": ["Unique Constraint", "Not Null Constraint", "Foreign Key Constraint", "Check Constraint"], "answer": "Foreign Key Constraint"},
            {"question": "What is the purpose of a database index?", "options": ["To sort data on screen only", "To speed up data retrieval operations", "To encrypt table columns", "To back up database tables"], "answer": "To speed up data retrieval operations"}
        ],
        "Network Protocols": [
            {"question": "At which layer of the TCP/IP model does HTTP operate?", "options": ["Network Access Layer", "Transport Layer", "Internet Layer", "Application Layer"], "answer": "Application Layer"},
            {"question": "Which protocol is connection-oriented and guarantees reliable data delivery?", "options": ["UDP", "TCP", "IP", "ICMP"], "answer": "TCP"},
            {"question": "What is the purpose of the Address Resolution Protocol (ARP)?", "options": ["Resolving domain names to IP addresses", "Mapping an IP address to a physical MAC address", "Routing packets across networks", "Securing browser connections"], "answer": "Mapping an IP address to a physical MAC address"},
            {"question": "Which port is standard for HTTPS communication?", "options": ["80", "21", "443", "8080"], "answer": "443"},
            {"question": "What is the main function of the Border Gateway Protocol (BGP)?", "options": ["Routing data between different autonomous systems on the internet", "Assigning IP addresses to local client devices", "Resolving local hostnames", "Encrypting email messages"], "answer": "Routing data between different autonomous systems on the internet"}
        ],
        "Artificial Intelligence": [
            {"question": "Which search algorithm is guaranteed to find the shortest path in an unweighted graph?", "options": ["Depth First Search (DFS)", "Breadth First Search (BFS)", "Greedy Best-First Search", "Hill Climbing"], "answer": "Breadth First Search (BFS)"},
            {"question": "In game theory, what does the Minimax algorithm do?", "options": ["Increases the search speed", "Minimizes the possible loss for a worst-case scenario", "Selects a random move", "Deletes nodes from the search tree"], "answer": "Minimizes the possible loss for a worst-case scenario"},
            {"question": "What is a heuristic function in AI search?", "options": ["An exact mathematical formula for calculation", "A rule of thumb or estimate to guide search efficiency", "A function that generates random values", "An encryption algorithm"], "answer": "A rule of thumb or estimate to guide search efficiency"},
            {"question": "Which representation is used in First-Order Logic to specify relationships?", "options": ["Predicates and Quantifiers", "Strictly binary bits", "Truth tables only", "CSS styles"], "answer": "Predicates and Quantifiers"},
            {"question": "What is expert systems in AI?", "options": ["Software that simulates human decision-making and expertise", "High-performance gaming computers", "Data storage centers", "Network routing software"], "answer": "Software that simulates human decision-making and expertise"}
        ],
        "Computer Graphics": [
            {"question": "Which algorithm is commonly used for line drawing in computer graphics?", "options": ["Bresenham's Line Algorithm", "Dijkstra's Algorithm", "Kruskal's Algorithm", "Binary Search"], "answer": "Bresenham's Line Algorithm"},
            {"question": "What is ray tracing?", "options": ["A method to speed up database queries", "A rendering technique for generating images by tracing paths of light", "A technique to debug network traffic", "A method for drawing circles quickly"], "answer": "A rendering technique for generating images by tracing paths of light"},
            {"question": "What are the primary colors in the RGB color model used for digital screens?", "options": ["Red, Green, Blue", "Red, Yellow, Blue", "Cyan, Magenta, Yellow", "Red, Green, Yellow"], "answer": "Red, Green, Blue"},
            {"question": "What is rendering in computer graphics?", "options": ["Generating a 2D image from a 3D model using computer programs", "Writing compiler code", "Scanning physical photos", "Connecting graphics cables"], "answer": "Generating a 2D image from a 3D model using computer programs"},
            {"question": "What is a pixel?", "options": ["A type of vector graphic", "The smallest addressable element in a raster image", "A unit of CPU speed", "A database query language command"], "answer": "The smallest addressable element in a raster image"}
        ]
    }
}


def get_default_department(user_department):
    if user_department and user_department in DEPARTMENTS:
        return user_department
    return next(iter(DEPARTMENTS.keys()))


def get_courses_for_department(department):
    return DEPARTMENTS.get(department, {}).get("courses", {})


def get_quiz_questions(department, course, count=5, difficulty="Easy"):
    syllabus = DEPARTMENTS.get(department, {}).get("courses", {}).get(course, "")

    if api_key:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            uniqueness_seed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            prompt = f"""Generate {count} multiple-choice quiz questions.
Department: {DEPARTMENTS.get(department, {}).get('name', department)}
Course: {course}
Syllabus Topics: {syllabus}
Difficulty Level: {difficulty}
Unique Seed: {uniqueness_seed}

Rules:
1. Return ONLY valid JSON array.
2. Each item must have exactly these keys: question, options, answer.
3. options must have exactly 4 distinct strings.
4. answer must exactly match one of the options.
5. Keep questions clear and suitable for undergraduate students.
6. The difficulty of the questions must be strictly '{difficulty}'.

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
DATA_DIR = os.getenv("DATA_DIR", ".")
PAST_PAPERS_FILE = os.path.join(DATA_DIR, "past_papers.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

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

    remaining_seconds = 0
    if active_quiz:
        elapsed = time.time() - active_quiz.get('start_time', time.time())
        remaining = active_quiz.get('time_limit', 300) - elapsed
        remaining_seconds = max(0, int(remaining))

    return render_template(
        "student_dashboard.html",
        papers=filtered_papers,
        user=session.get('name'),
        departments=DEPARTMENTS,
        selected_department=selected_department,
        selected_course=selected_course,
        courses=courses,
        active_quiz=active_quiz,
        quiz_result=quiz_result,
        remaining_seconds=remaining_seconds
    )


@app.route("/student/quiz/start", methods=["POST"])
def start_student_quiz():
    if 'user' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    department = request.form.get("department", "").strip()
    course = request.form.get("course", "").strip()
    difficulty = request.form.get("difficulty", "Easy").strip()
    limit_str = request.form.get("limit", "5").strip()

    try:
        limit = int(limit_str)
        if limit <= 0:
            limit = 5
    except ValueError:
        limit = 5

    if department not in DEPARTMENTS:
        return redirect(url_for('student_dashboard'))

    if course not in DEPARTMENTS[department]["courses"]:
        return redirect(url_for('student_dashboard', department=department))

    # Calculate time limit in seconds
    # Easy: 3 mins for 5 questions (36 seconds per question)
    # Moderate/Medium: 5 mins for 5 questions (60 seconds per question)
    # Hard: 10 mins for 5 questions (120 seconds per question)
    if difficulty == "Easy":
        time_limit = limit * 36
    elif difficulty in ["Medium", "Moderate"]:
        time_limit = limit * 60
    else: # Hard
        time_limit = limit * 120

    questions = get_quiz_questions(department, course, count=limit, difficulty=difficulty)
    session['active_quiz'] = {
        "department": department,
        "course": course,
        "difficulty": difficulty,
        "time_limit": time_limit,
        "start_time": time.time(),
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

    has_error = False
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        output = response.text
    except Exception as e:
        error_str = str(e)
        # If quota exceeded or API error, use fallback generator
        if "429" in error_str or "quota" in error_str.lower() or "rate_limit" in error_str.lower():
            output = generate_fallback_questions(course, syllabus, two_marks, five_marks, ten_marks)
        else:
            output = f"Error: {str(e)}"
            has_error = True

    try:
        papers = load_past_papers()
        user_dept = session.get('department', 'AI&DS')
        
        if has_error:
            # If generation failed, return dashboard with error message and do not save paper
            staff_papers = [item for item in papers if item.get('department') == user_dept]
            staff_papers.sort(key=lambda item: item.get('id', 0), reverse=True)
            return render_template(
                "staff_dashboard.html",
                output=output,
                success=False,
                user=session.get('name'),
                user_dept=user_dept,
                departments=DEPARTMENTS,
                staff_papers=staff_papers
            )

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

        staff_papers = [item for item in papers if item.get('department') == user_dept]
        staff_papers.sort(key=lambda item: item.get('id', 0), reverse=True)
        return render_template(
            "staff_dashboard.html",
            output=output,
            success=True,
            paper_id=paper["id"],
            paper_published=paper["published"],
            user=session.get('name'),
            user_dept=user_dept,
            departments=DEPARTMENTS,
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
