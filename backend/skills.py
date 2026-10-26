import re

SKILLS = {
    "Python": r"python", "Java": r"java(?!script)", "JavaScript": r"javascript|\bjs\b", "TypeScript": r"typescript",
    "C++": r"c\+\+|cpp", "C#": r"c#|\.net|dotnet", "C": r"(?-i:\bC\b)(?=,|/| and| or| programming)", "Go": r"golang|(?-i:\bGo\b)(?=,|/| \(| and| or| developer| engineer)",
    "Rust": r"\brust\b", "Ruby": r"\bruby\b", "Rails": r"rails", "PHP": r"\bphp\b", "Kotlin": r"kotlin", "Swift": r"\bswift\b",
    "Scala": r"\bscala\b", "R": r"(?-i:\bR\b)(?=,|/| and| or| programming)", "Dart": r"\bdart\b", "Elixir": r"elixir", "Perl": r"\bperl\b",
    "React": r"react(?:\.js|js)?(?! native)", "React Native": r"react native", "Next.js": r"next\.?js", "Vue": r"vue(?:\.js)?",
    "Angular": r"angular", "Svelte": r"svelte", "Redux": r"redux", "HTML": r"\bhtml5?\b", "CSS": r"\bcss3?\b", "Tailwind": r"tailwind",
    "Node.js": r"node\.?js|\bnode\b", "Express": r"express(?:\.js)?\b", "Django": r"django", "Flask": r"\bflask\b", "FastAPI": r"fastapi",
    "Spring": r"spring boot|\bspring\b", "Laravel": r"laravel", "GraphQL": r"graphql", "REST APIs": r"rest(?:ful)? api|\bapis?\b",
    "gRPC": r"grpc", "Microservices": r"microservices?", "SQL": r"\bsql\b", "PostgreSQL": r"postgres(?:ql)?", "MySQL": r"mysql",
    "MongoDB": r"mongo(?:db)?", "Redis": r"\bredis\b", "Cassandra": r"cassandra", "DynamoDB": r"dynamodb", "Elasticsearch": r"elasticsearch",
    "Kafka": r"kafka", "RabbitMQ": r"rabbitmq", "Snowflake": r"snowflake", "BigQuery": r"bigquery", "Spark": r"\bspark\b|pyspark",
    "Hadoop": r"hadoop", "Airflow": r"airflow", "dbt": r"\bdbt\b", "AWS": r"\baws\b|amazon web services", "GCP": r"\bgcp\b|google cloud",
    "Azure": r"\bazure\b", "Docker": r"docker", "Kubernetes": r"kubernetes|\bk8s\b", "Terraform": r"terraform", "CI/CD": r"ci/cd|continuous integration",
    "Jenkins": r"jenkins", "Git": r"\bgit\b|github|gitlab", "Linux": r"linux|unix", "Bash": r"\bbash\b|shell scripting",
    "Machine Learning": r"machine learning|\bml\b", "Deep Learning": r"deep learning", "NLP": r"\bnlp\b|natural language processing",
    "Computer Vision": r"computer vision", "LLMs": r"\bllms?\b|large language model|generative ai|genai", "PyTorch": r"pytorch",
    "TensorFlow": r"tensorflow", "scikit-learn": r"scikit|sklearn", "Pandas": r"pandas", "NumPy": r"numpy", "Data Science": r"data scien",
    "Data Analysis": r"data analy", "Statistics": r"statistic", "Tableau": r"tableau", "Power BI": r"power ?bi", "Excel": r"\bexcel\b",
    "DSA": r"data structures|algorithms", "System Design": r"system design|distributed systems", "OOP": r"object[- ]oriented|\boop\b",
    "Android": r"android", "iOS": r"\bios\b", "Flutter": r"flutter", "Figma": r"figma", "UI/UX": r"ui/ux|ux design|user experience",
    "Agile": r"agile|scrum", "Security": r"cybersecurity|application security|infosec", "Testing": r"unit test|test automation|selenium|cypress|jest",
    "Blockchain": r"blockchain|web3|solidity", "Salesforce": r"salesforce", "SAP": r"\bsap\b", "Product Management": r"product management",
}

SKILLS.update({
    "Sales": r"\bsales\b", "Lead Generation": r"lead generation|prospecting", "Negotiation": r"negotiat", "CRM": r"\bcrm\b|hubspot|zoho crm",
    "Account Management": r"account management", "B2B Sales": r"\bb2b\b", "Cold Calling": r"cold call", "Digital Marketing": r"digital marketing",
    "SEO": r"\bseo\b|search engine optimi", "SEM": r"\bsem\b|google ads|ppc", "Social Media Marketing": r"social media", "Content Writing": r"content writ|copywrit",
    "Google Analytics": r"google analytics|\bga4\b", "Email Marketing": r"email marketing|mailchimp", "Brand Management": r"brand management|branding",
    "Market Research": r"market research", "Public Relations": r"public relations", "Accounting": r"accounting|bookkeeping", "Tally": r"\btally\b",
    "GST": r"\bgst\b", "Taxation": r"taxation|tax return|income tax", "Auditing": r"\baudit", "Financial Analysis": r"financial (analysis|modell?ing)",
    "Financial Reporting": r"financial (reporting|statements)", "IFRS": r"\bifrs\b|\bgaap\b", "QuickBooks": r"quickbooks", "Budgeting": r"budget",
    "Risk Management": r"risk management", "Credit Analysis": r"credit (analysis|risk|appraisal)", "KYC/AML": r"\bkyc\b|\baml\b|anti.money", "Compliance": r"compliance",
    "Underwriting": r"underwrit", "Recruitment": r"recruit|talent acquisition|sourcing candidates", "Payroll": r"payroll", "Onboarding": r"onboarding",
    "Employee Relations": r"employee relations", "HRIS": r"\bhris\b|workday|bamboohr", "Training & Development": r"training (and|&) development|\bl&d\b",
    "Project Management": r"project management|\bpmp\b", "Stakeholder Management": r"stakeholder", "Business Analysis": r"business analysis|requirements gathering",
    "Jira": r"\bjira\b", "Process Improvement": r"process improvement|lean|six sigma", "Adobe Photoshop": r"photoshop", "Adobe Illustrator": r"illustrator",
    "Premiere Pro": r"premiere pro", "After Effects": r"after effects", "Canva": r"\bcanva\b", "Video Editing": r"video edit", "Photography": r"photograph",
    "Copywriting": r"copywrit", "Editing & Proofreading": r"proofread", "Patient Care": r"patient care", "Clinical Documentation": r"clinical documentation|charting|\bemr\b|\behr\b",
    "Medical Terminology": r"medical terminology", "Medical Coding": r"medical coding|icd-?10|\bcpt\b", "BLS/CPR": r"\bbls\b|\bcpr\b|basic life support",
    "Phlebotomy": r"phlebotom", "Pharmacology": r"pharmacolog|dispensing", "Infection Control": r"infection control", "Lesson Planning": r"lesson plan",
    "Classroom Management": r"classroom management", "Curriculum Design": r"curriculum", "Tutoring": r"tutor", "AutoCAD": r"autocad", "Revit": r"\brevit\b",
    "STAAD Pro": r"staad", "SolidWorks": r"solidworks", "CATIA": r"\bcatia\b", "MATLAB": r"matlab", "PLC": r"\bplc\b", "SCADA": r"scada",
    "Quantity Surveying": r"quantity survey|estimation", "Site Supervision": r"site supervision|site execution", "Quality Control": r"quality control|\bqc\b|quality assurance",
    "Preventive Maintenance": r"preventive maintenance", "Inventory Management": r"inventory", "Procurement": r"procure|purchasing", "Logistics": r"logistic",
    "Warehouse Operations": r"warehouse", "Demand Planning": r"demand plann|forecasting", "SAP MM": r"sap mm", "Customer Service": r"customer service|customer care",
    "Communication": r"communication skills|excellent communication", "Complaint Handling": r"complaint", "Zendesk": r"zendesk|freshdesk", "Upselling": r"upsell|cross-sell",
    "Merchandising": r"merchandis", "POS": r"point of sale|\bpos\b", "Food Safety": r"food safety|haccp|hygiene", "Guest Relations": r"guest relations|front office",
    "Cooking": r"culinary|cooking", "Event Management": r"event (management|planning)", "Electrical Wiring": r"wiring|electrical installation", "Welding": r"weld",
    "Plumbing": r"plumb", "HVAC": r"hvac", "CNC Machining": r"\bcnc\b", "Workplace Safety": r"\bosha\b|safety procedures|\bppe\b|lockout", "Troubleshooting": r"troubleshoot",
    "Driving": r"driving licen[cs]e|\bcdl\b", "Route Planning": r"route plann", "Legal Research": r"legal research", "Contract Drafting": r"contract (drafting|review)|drafting",
    "Litigation": r"litigation", "Corporate Law": r"corporate law", "Data Privacy": r"\bgdpr\b|data privacy", "Laboratory Techniques": r"laboratory|\bpcr\b|chromatograph",
    "Research Methodology": r"research method", "Agronomy": r"agronom|crop", "Sustainability": r"sustainab|\besg\b", "Fashion Design": r"fashion design|pattern making",
    "Makeup": r"makeup", "Hair Styling": r"hair (styling|cutting)", "Teaching": r"\bteaching\b", "Leadership": r"team lead|people management|leadership",
})

_COMPILED = [(name, re.compile(pat, re.I)) for name, pat in SKILLS.items()]
_LOWER_MAP = {k.lower(): k for k in SKILLS}


def extract_skills(text: str, limit: int = 18) -> list:
    if not text:
        return []
    text = text[:12000]
    found = []
    for name, rx in _COMPILED:
        m = rx.search(text)
        if m:
            found.append((m.start(), name))
    found.sort()
    return [n for _, n in found][:limit]


def canonical(skill: str) -> str:
    s = skill.strip()
    if s.lower() in _LOWER_MAP:
        return _LOWER_MAP[s.lower()]
    found = extract_skills(s)
    return found[0] if len(found) == 1 else s
