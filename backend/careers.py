"""Career taxonomy: sectors, roles, job classification, OA templates, interview styles and match weights.
Built-in defaults live here; admins can add/override sectors in Mongo (career_sectors) without code changes."""
import re

W_DEFAULT = {"skills": 45, "role": 20, "sector": 10, "experience": 15, "location": 10}

# section: (name, types, focus). types: mcq | numeric | written. coding problems are separate (coding=True).
S = lambda name, types, focus: {"name": name, "types": types, "focus": focus}
APT = S("Aptitude", ["mcq", "numeric"], "quantitative aptitude, logical reasoning and data interpretation")
SJT = S("Situational Judgement", ["mcq"], "realistic workplace situations with best-response options")

SECTORS = [
    {"id": "tech", "name": "Technology & IT", "coding": True,
     "roles": ["Software Engineer", "Frontend Developer", "Backend Developer", "Full-Stack Developer", "Java Developer", "Python Developer", "Mobile App Developer", "QA Engineer", "Automation Tester", "DevOps Engineer", "Cloud Engineer", "Cybersecurity Analyst", "Network Engineer", "Database Administrator", "Technical Support Engineer", "AI Engineer", "Machine Learning Engineer"],
     "kw": r"software|developer|programmer|\bsde\b|engineer.*(software|backend|frontend|full.?stack|platform|devops|cloud|site reliability|security|network|qa|test|ml|ai|data)|devops|\bsre\b|frontend|backend|full.?stack|cyber|infosec|cloud|\bqa\b|tester|android|ios developer|web developer|machine learning|\bml\b|\bai\b engineer|database admin|\bdba\b|it support|technical support|sysadmin|system administrator",
     "oa": [S("Technical MCQ", ["mcq"], "core CS, the role's languages/frameworks, databases and debugging"), S("SQL & Debugging", ["mcq", "written"], "SQL queries, reading code, finding bugs"), APT],
     "oa_types": ["Full OA", "Coding only", "Technical MCQ", "Aptitude"], "styles": ["Technical", "Mixed", "HR", "Behavioral", "Managerial"],
     "competencies": ["Technical knowledge", "Problem solving", "Code quality", "System thinking", "Communication"]},
    {"id": "data", "name": "Data & Analytics", "coding": True,
     "roles": ["Data Analyst", "Data Scientist", "Data Engineer", "Business Intelligence Analyst", "Marketing Analyst"],
     "kw": r"data (analyst|scientist|engineer|analytics)|business intelligence|\bbi\b analyst|analytics engineer|statistician|quantitative analyst",
     "oa": [S("Excel & Spreadsheets", ["mcq", "numeric"], "formulas, lookups, pivot tables, cleaning data"), S("SQL", ["mcq", "written"], "writing and reading SQL queries on a small described schema"),
            S("Statistics & Data Interpretation", ["mcq", "numeric"], "descriptive stats, probability, reading a described table/chart"), S("Business Case", ["written"], "turn a small dataset/situation into insights and a recommendation")],
     "oa_types": ["Full OA", "Excel & SQL", "Statistics", "Case study", "Coding only"], "styles": ["Technical", "Case", "Mixed", "Behavioral"],
     "competencies": ["SQL & Excel", "Statistics", "Data storytelling", "Business sense", "Communication"]},
    {"id": "sales", "name": "Business, Sales & Marketing",
     "roles": ["Sales Executive", "Business Development Executive", "Account Manager", "Territory Sales Manager", "Sales Representative", "Digital Marketing Executive", "SEO Specialist", "Performance Marketer", "Social Media Manager", "Brand Manager", "Content Marketer", "Market Research Analyst", "Public Relations Executive"],
     "kw": r"sales|business development|\bbdr\b|\bsdr\b|account (manager|executive)|marketing|\bseo\b|\bsem\b|growth|brand|social media|content market|public relations|\bpr\b|market research|campaign|demand generation|partnerships",
     "oa": [S("Sales & Marketing Scenarios", ["mcq"], "lead qualification, objection handling, campaign choices, negotiation, retention"), S("Written Pitch / Campaign Task", ["written"], "write a short product pitch, cold email or campaign plan"),
            S("Marketing Analytics", ["mcq", "numeric"], "conversion rates, CAC, ROI, funnel and keyword metrics"), SJT],
     "oa_types": ["Full OA", "Role-play scenarios", "Marketing analytics", "Situational judgement"], "styles": ["Role-play", "Mixed", "Behavioral", "HR", "Managerial"],
     "competencies": ["Communication", "Persuasion", "Customer understanding", "Objection handling", "Results orientation"],
     "w": {"skills": 30, "role": 25, "sector": 15, "experience": 20, "location": 10}},
    {"id": "finance", "name": "Finance, Banking & Insurance",
     "roles": ["Accountant", "Financial Analyst", "Chartered Accountant", "Auditor", "Tax Consultant", "Bank PO", "Bank Clerk", "Relationship Manager", "Credit Analyst", "Investment Analyst", "Insurance Advisor", "Claims Analyst", "Risk Analyst", "Compliance Officer", "Financial Planner"],
     "kw": r"account(ant|ing)|financ|audit|\btax|banking|\bbank\b|credit|investment|insurance|claims|underwrit|risk analyst|treasury|payable|receivable|bookkeep|controller|fp&a|actuar|wealth|loan",
     "oa": [S("Numerical Aptitude", ["mcq", "numeric"], "percentages, interest, ratios, financial arithmetic"), S("Accounting & Finance Fundamentals", ["mcq"], "accounting principles, journal entries, statements, taxation basics"),
            S("Financial Statement Interpretation", ["mcq", "numeric", "written"], "read a described P&L/balance sheet and interpret it"), S("Risk & Compliance Scenarios", ["mcq"], "KYC, fraud, compliance and ethics situations")],
     "oa_types": ["Full OA", "Numerical aptitude", "Accounting fundamentals", "Case study"], "styles": ["Technical", "Case", "Mixed", "Behavioral", "HR"],
     "competencies": ["Accounting/finance knowledge", "Numerical accuracy", "Analytical reasoning", "Compliance awareness", "Communication"],
     "w": {"skills": 40, "role": 20, "sector": 10, "experience": 20, "location": 10}},
    {"id": "hr", "name": "Human Resources & Recruitment",
     "roles": ["HR Executive", "HR Manager", "Talent Acquisition Specialist", "Technical Recruiter", "Recruitment Consultant", "Payroll Specialist", "HR Analyst", "Learning and Development Specialist", "Training Manager"],
     "kw": r"\bhr\b|human resources|recruit|talent acquisition|people (partner|operations)|payroll|hrbp|learning (and|&) development|\bl&d\b|compensation|benefits",
     "oa": [S("HR Fundamentals", ["mcq"], "HR processes, labour-law basics, payroll, onboarding"), S("Recruitment Scenarios", ["mcq", "written"], "screening candidates, writing a job post, sourcing"), SJT, APT],
     "oa_types": ["Full OA", "Recruitment scenarios", "Situational judgement"], "styles": ["Behavioral", "Scenario", "HR", "Mixed"],
     "competencies": ["People judgement", "HR knowledge", "Conflict resolution", "Communication", "Confidentiality & ethics"]},
    {"id": "product", "name": "Product, Project & Operations",
     "roles": ["Product Manager", "Associate Product Manager", "Project Manager", "Program Manager", "Scrum Master", "Business Analyst", "Operations Manager", "Management Consultant", "Process Improvement Analyst", "Implementation Manager"],
     "kw": r"product manager|product owner|project manager|program manager|scrum master|business analyst|operations (manager|analyst|lead)|management consultant|strategy (manager|analyst)|implementation manager|process improvement|\bpmo\b|chief of staff",
     "oa": [S("Product & Business Case", ["written"], "prioritisation, metrics, a short product or process case"), S("Analytical Reasoning", ["mcq", "numeric"], "metrics, estimation and data interpretation"), S("Project Management", ["mcq"], "planning, agile, risk, stakeholders"), SJT],
     "oa_types": ["Full OA", "Case study", "Analytical reasoning", "Situational judgement"], "styles": ["Case", "Behavioral", "Managerial", "Mixed"],
     "competencies": ["Structured thinking", "Prioritisation", "Stakeholder management", "Metrics & data", "Leadership"]},
    {"id": "design", "name": "Design, Media & Creative",
     "roles": ["Graphic Designer", "UI/UX Designer", "Product Designer", "Animator", "Video Editor", "Photographer", "Content Writer", "Copywriter", "Technical Writer", "Journalist", "Motion Graphics Designer", "3D Artist", "Creative Director"],
     "kw": r"design(er)?|\bux\b|\bui\b|illustrat|animat|video editor|motion graphic|photograph|content writer|copywrit|technical writer|journalis|editor|3d artist|creative director|art director",
     "oa": [S("Design / Craft Knowledge", ["mcq"], "principles, tools, typography, UX heuristics or writing craft for the role"), S("Design Brief / Writing Task", ["written"], "respond to a brief: approach, concept, rationale or a short piece of copy"), S("Critique & UX Reasoning", ["mcq", "written"], "critique a described design or content piece")],
     "oa_types": ["Full OA", "Design brief", "Writing task", "Craft knowledge"], "styles": ["Portfolio", "Behavioral", "Mixed", "HR"],
     "competencies": ["Craft quality", "Creative thinking", "User/audience focus", "Feedback handling", "Communication"],
     "w": {"skills": 40, "role": 25, "sector": 10, "experience": 15, "location": 10}},
    {"id": "healthcare", "name": "Healthcare & Medicine",
     "roles": ["Doctor", "Nurse", "Pharmacist", "Physiotherapist", "Medical Lab Technician", "Radiology Technician", "Medical Coder", "Medical Biller", "Hospital Administrator", "Healthcare Analyst", "Nutritionist", "Clinical Research Associate", "Medical Representative", "Public Health Officer"],
     "kw": r"nurs|doctor|physician|medical|clinic|pharma|hospital|health ?care|patient|physiother|radiolog|dental|therapist|caregiver|lab technician|phlebotom|nutrition|dietitian|public health|\brn\b|\bmd\b",
     "oa": [S("Professional Knowledge", ["mcq"], "role-appropriate clinical/medical knowledge and terminology"), S("Workplace & Patient Scenarios", ["mcq", "written"], "patient communication, documentation, prioritisation"), S("Safety & Ethics", ["mcq"], "infection control, consent, confidentiality, patient safety")],
     "oa_types": ["Full OA", "Professional knowledge", "Patient scenarios", "Safety & ethics"], "styles": ["Scenario", "Behavioral", "Technical", "HR"],
     "competencies": ["Professional knowledge", "Patient safety", "Communication & empathy", "Ethics", "Teamwork"],
     "note": "Practice only. AI-generated clinical content is not medical guidance and does not replace qualified supervision or official exams.",
     "w": {"skills": 35, "role": 25, "sector": 15, "experience": 15, "location": 10}},
    {"id": "education", "name": "Education & Training",
     "roles": ["School Teacher", "College Lecturer", "Professor", "Tutor", "Academic Counselor", "Career Counselor", "Instructional Designer", "Curriculum Developer", "Corporate Trainer", "Education Consultant", "Competitive Exam Faculty"],
     "kw": r"teacher|teaching|lecturer|professor|tutor|faculty|educat|instructional design|curriculum|trainer|counsel(l)?or|academic|school",
     "oa": [S("Subject Knowledge", ["mcq", "numeric"], "the subject the candidate will teach, at the right grade level"), S("Pedagogy & Classroom Management", ["mcq"], "teaching methods, assessment, classroom situations"), S("Lesson Planning", ["written"], "write a short lesson plan or explain a concept for a given class")],
     "oa_types": ["Full OA", "Subject knowledge", "Pedagogy", "Lesson planning"], "styles": ["Teaching demo", "Scenario", "Behavioral", "HR"],
     "competencies": ["Subject mastery", "Pedagogy", "Classroom management", "Communication", "Empathy"]},
    {"id": "civil", "name": "Civil Engineering & Construction",
     "roles": ["Civil Engineer", "Structural Engineer", "Site Engineer", "Architect", "Interior Designer", "Construction Manager", "Quantity Surveyor", "BIM Engineer", "Planning Engineer", "Safety Engineer", "Surveyor", "Urban Planner"],
     "kw": r"civil engineer|structural|site engineer|architect(?!ure)|construction|quantity surveyor|\bbim\b|surveyor|urban plann|interior design|\bhse\b|safety engineer",
     "oa": [S("Engineering Fundamentals", ["mcq", "numeric"], "materials, structures, estimation, codes and standards"), S("Site & Project Scenarios", ["mcq", "written"], "planning, quality issues, site problems"), S("Safety", ["mcq"], "construction safety practices")],
     "oa_types": ["Full OA", "Engineering fundamentals", "Site scenarios", "Safety"], "styles": ["Technical", "Scenario", "Behavioral", "HR"],
     "competencies": ["Engineering knowledge", "Numerical problem solving", "Safety awareness", "Planning", "Communication"]},
    {"id": "core_eng", "name": "Mechanical, Electrical & Electronics",
     "roles": ["Mechanical Engineer", "Electrical Engineer", "Electronics Engineer", "Automotive Engineer", "Aerospace Engineer", "Robotics Engineer", "Embedded Systems Engineer", "VLSI Engineer", "Production Engineer", "Maintenance Engineer", "Quality Engineer", "CAD/CAM Engineer"],
     "kw": r"mechanical|electrical engineer|electronics|automotive engineer|aerospace|robotic|embedded|vlsi|firmware|hardware engineer|production engineer|maintenance engineer|quality engineer|cad|manufacturing engineer|process engineer",
     "oa": [S("Engineering Fundamentals", ["mcq", "numeric"], "core principles of the discipline with numerical problems"), S("Troubleshooting Scenarios", ["mcq", "written"], "diagnose a described fault or quality issue"), S("Quality, Maintenance & Safety", ["mcq"], "QA methods, maintenance practice, safety")],
     "oa_types": ["Full OA", "Engineering fundamentals", "Troubleshooting", "Safety & quality"], "styles": ["Technical", "Scenario", "Behavioral", "HR"],
     "competencies": ["Engineering knowledge", "Troubleshooting", "Numerical problem solving", "Quality & safety", "Communication"]},
    {"id": "supply", "name": "Manufacturing, Logistics & Supply Chain",
     "roles": ["Supply Chain Analyst", "Procurement Officer", "Warehouse Manager", "Inventory Controller", "Logistics Coordinator", "Demand Planner", "Production Supervisor", "Quality Inspector", "Fleet Manager", "Import-Export Executive"],
     "kw": r"supply chain|procure|purchas|warehouse|inventory|logistic|demand plann|production supervisor|quality inspector|import|export|sourcing|fulfil?ment|operations associate",
     "oa": [S("Operations Knowledge", ["mcq"], "inventory, procurement, logistics and quality concepts"), S("Numerical Operations", ["mcq", "numeric"], "stock levels, lead times, costs, forecasting arithmetic"), S("Operations Scenarios", ["mcq", "written"], "handle a delay, stock-out or supplier issue")],
     "oa_types": ["Full OA", "Operations scenarios", "Numerical", "Situational judgement"], "styles": ["Scenario", "Technical", "Behavioral", "Managerial"],
     "competencies": ["Operations knowledge", "Planning", "Numerical accuracy", "Problem solving", "Communication"]},
    {"id": "hospitality", "name": "Hospitality, Tourism & Aviation",
     "roles": ["Hotel Manager", "Receptionist", "Guest Relations Executive", "Chef", "Restaurant Manager", "Travel Consultant", "Tour Guide", "Cabin Crew", "Airport Ground Staff", "Event Coordinator", "Housekeeping Supervisor"],
     "kw": r"hotel|hospitality|reception|front desk|guest|chef|cook|restaurant|barista|travel|tour|cabin crew|flight attendant|airport|ground staff|event|housekeep|concierge",
     "oa": [S("Service Standards", ["mcq"], "guest service, hygiene, safety and service standards"), S("Guest Scenarios", ["mcq", "written"], "handle a complaint, overbooking or special request"), SJT],
     "oa_types": ["Full OA", "Guest role-play", "Situational judgement"], "styles": ["Role-play", "Scenario", "Behavioral", "HR"],
     "competencies": ["Service mindset", "Communication", "Composure", "Hygiene & safety", "Teamwork"],
     "w": {"skills": 25, "role": 25, "sector": 15, "experience": 20, "location": 15}},
    {"id": "retail", "name": "Retail & E-commerce",
     "roles": ["Store Manager", "Retail Associate", "Cashier", "Merchandiser", "Category Manager", "E-commerce Executive", "Marketplace Manager", "Catalog Executive", "Retail Operations Manager", "Buyer"],
     "kw": r"retail|store (manager|associate)|cashier|merchandis|category manager|e-?commerce|marketplace|catalog|buyer|shop|sales associate",
     "oa": [S("Retail & E-commerce Knowledge", ["mcq"], "merchandising, inventory, marketplace operations"), S("Numerical", ["mcq", "numeric"], "margins, discounts, stock and sales arithmetic"), S("Customer Scenarios", ["mcq", "written"], "returns, complaints, upselling")],
     "oa_types": ["Full OA", "Customer scenarios", "Numerical"], "styles": ["Role-play", "Scenario", "Behavioral", "HR"],
     "competencies": ["Customer service", "Commercial sense", "Numerical accuracy", "Reliability", "Communication"],
     "w": {"skills": 25, "role": 25, "sector": 15, "experience": 20, "location": 15}},
    {"id": "support", "name": "Customer Service & BPO",
     "roles": ["Customer Support Executive", "Customer Success Manager", "Call Center Agent", "Chat Support Agent", "Technical Support Representative", "Help Desk Executive", "Customer Experience Analyst", "Complaint Resolution Specialist"],
     "kw": r"customer (support|service|success|experience|care)|call cent|contact cent|chat support|help ?desk|\bbpo\b|complaint|client support|support (agent|specialist|representative)",
     "oa": [S("Communication & English", ["mcq"], "grammar, comprehension, tone"), S("Email / Chat Responses", ["written"], "reply to a customer message professionally"), S("Complaint & Escalation Scenarios", ["mcq"], "choose the best way to resolve or escalate")],
     "oa_types": ["Full OA", "Chat/email simulation", "Communication", "Situational judgement"], "styles": ["Role-play", "Scenario", "Behavioral", "HR"],
     "competencies": ["Communication", "Empathy", "Problem resolution", "Composure", "Product understanding"],
     "w": {"skills": 25, "role": 25, "sector": 15, "experience": 20, "location": 15}},
    {"id": "government", "name": "Government & Public Sector",
     "roles": ["Civil Services (UPSC)", "State PCS", "SSC CGL", "SSC CHSL", "Railway Recruitment (RRB)", "Banking Exams (IBPS/SBI)", "Government Teaching (TET)", "PSU Recruitment", "Police Recruitment", "Defence Recruitment", "Court Clerk", "Public Administration"],
     "kw": r"government|public sector|civil service|municipal|\bpsu\b|ministry|federal|state of|county|city of|public administration|police|defen[cs]e|court",
     "oa": [S("Quantitative Aptitude", ["mcq", "numeric"], "arithmetic, algebra, data interpretation"), S("Logical Reasoning", ["mcq"], "verbal and non-verbal reasoning"), S("General Awareness", ["mcq"], "static GK, polity, economy, history, geography (avoid fast-changing current affairs)"), S("English Language", ["mcq"], "grammar, vocabulary, comprehension")],
     "oa_types": ["Full mock test", "Quantitative aptitude", "Reasoning", "General awareness", "English"], "styles": ["Government", "Behavioral", "HR"],
     "competencies": ["Awareness", "Reasoning", "Ethics & integrity", "Communication", "Decision making"],
     "note": "Practice pattern based on commonly published exam structures. Always verify the current pattern, syllabus and eligibility in the official recruitment notification.",
     "w": {"skills": 25, "role": 30, "sector": 20, "experience": 10, "location": 15}},
    {"id": "legal", "name": "Law & Compliance",
     "roles": ["Advocate", "Legal Associate", "Corporate Lawyer", "Legal Researcher", "Paralegal", "Company Secretary", "Contract Analyst", "Compliance Analyst", "AML Analyst", "KYC Analyst", "Privacy Specialist"],
     "kw": r"legal|lawyer|attorney|advocate|counsel\b|paralegal|company secretary|contract (manager|analyst|specialist|administrator)|compliance|\baml\b|\bkyc\b|privacy|regulatory",
     "oa": [S("Legal Reasoning", ["mcq"], "principles applied to fact situations"), S("Contract & Case Analysis", ["mcq", "written"], "interpret a clause or summarise a short case"), S("Drafting", ["written"], "draft a short clause, notice or email appropriate to the role")],
     "oa_types": ["Full OA", "Legal reasoning", "Drafting", "Compliance scenarios"], "styles": ["Case", "Technical", "Behavioral", "HR"],
     "competencies": ["Legal knowledge", "Analytical reasoning", "Drafting", "Attention to detail", "Ethics"]},
    {"id": "agri", "name": "Agriculture, Food & Environment",
     "roles": ["Agriculture Officer", "Agronomist", "Agricultural Engineer", "Food Technologist", "Food Safety Officer", "Veterinary Professional", "Dairy Technologist", "Environmental Scientist", "Sustainability Analyst", "Renewable Energy Engineer", "Forestry Officer"],
     "kw": r"agri|agronom|farm|food (technolog|safety|scien)|veterinar|dairy|environment|sustainab|renewable|solar|wind energy|forest|climate|esg",
     "oa": [S("Domain Knowledge", ["mcq"], "core agriculture/food/environment concepts for the role"), S("Numerical & Data", ["mcq", "numeric"], "yields, doses, emissions, data interpretation"), S("Field / Lab Scenarios", ["mcq", "written"], "practical situations and safety")],
     "oa_types": ["Full OA", "Domain knowledge", "Field scenarios"], "styles": ["Technical", "Scenario", "Behavioral", "HR"],
     "competencies": ["Domain knowledge", "Practical judgement", "Data skills", "Safety & regulation", "Communication"]},
    {"id": "trades", "name": "Skilled Trades & Technical Services",
     "roles": ["Electrician", "Plumber", "Welder", "Fitter", "CNC Operator", "Machine Operator", "HVAC Technician", "Automotive Mechanic", "Solar Technician", "Appliance Repair Technician", "Carpenter", "Fabricator", "Field Service Technician"],
     "kw": r"electrician|plumb|weld|fitter|\bcnc\b|machine operator|machinist|hvac|mechanic|technician|carpent|fabricat|installer|field service|maintenance worker|lineman",
     "oa": [S("Trade Knowledge", ["mcq"], "tools, materials, equipment and trade practice"), S("Troubleshooting", ["mcq", "written"], "find the likely cause of a described fault and the fix"), S("Workplace Safety", ["mcq"], "PPE, lockout/tagout, hazards, safe procedures")],
     "oa_types": ["Full OA", "Trade knowledge", "Troubleshooting", "Safety"], "styles": ["Field service", "Scenario", "Behavioral", "HR"],
     "competencies": ["Trade knowledge", "Safety", "Troubleshooting", "Reliability", "Customer handling"],
     "w": {"skills": 35, "role": 25, "sector": 10, "experience": 15, "location": 15}},
    {"id": "transport", "name": "Transportation & Delivery",
     "roles": ["Delivery Partner", "Courier Executive", "Truck Driver", "Bus Driver", "Fleet Supervisor", "Transport Coordinator", "Dispatch Planner", "Transportation Operations Specialist"],
     "kw": r"driver|delivery|courier|truck|fleet|dispatch|transport|chauffeur|rider",
     "oa": [S("Road Safety & Rules", ["mcq"], "traffic rules, safe driving, vehicle checks"), S("Route & Operations", ["mcq", "numeric"], "routing, time/distance, load and schedule arithmetic"), SJT],
     "oa_types": ["Full OA", "Safety & rules", "Situational judgement"], "styles": ["Scenario", "Behavioral", "HR"],
     "competencies": ["Safety", "Reliability", "Planning", "Customer handling", "Composure"],
     "w": {"skills": 20, "role": 25, "sector": 15, "experience": 15, "location": 25}},
    {"id": "fashion", "name": "Fashion, Beauty & Personal Care",
     "roles": ["Fashion Designer", "Textile Designer", "Fashion Merchandiser", "Tailor", "Stylist", "Makeup Artist", "Hair Stylist", "Beautician", "Cosmetologist", "Beauty Therapist"],
     "kw": r"fashion|textile|apparel|tailor|stylist|makeup|hair|beaut|cosmetolog|salon|spa|garment",
     "oa": [S("Craft & Product Knowledge", ["mcq"], "materials, techniques, products and trends basics"), S("Client Scenarios", ["mcq", "written"], "consultation, complaints, hygiene"), S("Hygiene & Safety", ["mcq"], "sanitation, allergies, safe use of products/tools")],
     "oa_types": ["Full OA", "Client scenarios", "Craft knowledge"], "styles": ["Portfolio", "Role-play", "Behavioral", "HR"],
     "competencies": ["Craft skill", "Client communication", "Hygiene & safety", "Creativity", "Professionalism"]},
    {"id": "science", "name": "Science & Research",
     "roles": ["Research Scientist", "Research Assistant", "Chemist", "Biotechnologist", "Microbiologist", "Laboratory Technician", "Geologist", "Physicist", "Forensic Analyst", "Pharmaceutical Research Associate"],
     "kw": r"scientist|research(er| assistant| associate)|chemist|biotech|microbiolog|laborator|geolog|physicist|forensic|biolog",
     "oa": [S("Scientific Fundamentals", ["mcq", "numeric"], "core concepts of the discipline"), S("Experimental Design & Data", ["mcq", "written"], "design an experiment, interpret results"), S("Lab Safety & Methodology", ["mcq"], "safety, controls, research ethics")],
     "oa_types": ["Full OA", "Fundamentals", "Experimental design", "Lab safety"], "styles": ["Technical", "Scenario", "Behavioral", "HR"],
     "competencies": ["Scientific knowledge", "Experimental design", "Data interpretation", "Rigor & ethics", "Communication"]},
    {"id": "freelance", "name": "Entrepreneurship, Freelancing & Gig Work",
     "roles": ["Freelance Developer", "Freelance Designer", "Freelance Writer", "Freelance Video Editor", "Virtual Assistant", "Online Tutor", "Independent Consultant", "E-commerce Seller", "Small Business Owner", "Home Service Professional"],
     "kw": r"freelanc|contract(or)? |virtual assistant|gig|self-employed|independent consultant|online tutor",
     "oa": [S("Client & Business Basics", ["mcq"], "pricing, scoping, contracts, client communication"), S("Client Proposal", ["written"], "write a short proposal or reply to a client brief"), SJT],
     "oa_types": ["Full OA", "Client proposal", "Situational judgement"], "styles": ["Role-play", "Behavioral", "Mixed"],
     "competencies": ["Client communication", "Self-management", "Craft quality", "Pricing & scoping", "Reliability"]},
]

STYLE_PLANS = {
    "Role-play": ["intro", "roleplay", "roleplay", "situational", "roleplay", "behavioral", "roleplay", "situational", "behavioral", "roleplay"],
    "Case": ["intro", "resume", "case", "core", "case", "situational", "case", "behavioral", "case", "behavioral"],
    "Scenario": ["intro", "resume", "situational", "core", "situational", "behavioral", "situational", "core", "behavioral", "situational"],
    "Managerial": ["intro", "resume", "situational", "behavioral", "case", "behavioral", "situational", "behavioral", "case", "behavioral"],
    "Teaching demo": ["intro", "resume", "demo", "core", "situational", "demo", "behavioral", "core", "demo", "behavioral"],
    "Government": ["intro", "resume", "awareness", "situational", "awareness", "behavioral", "situational", "awareness", "behavioral", "situational"],
    "Field service": ["intro", "resume", "core", "situational", "problem", "core", "situational", "behavioral", "problem", "behavioral"],
    "Portfolio": ["intro", "resume", "resume", "core", "situational", "behavioral", "core", "resume", "behavioral", "situational"],
}

_custom = {}
_RX = {}


def _all():
    out = {s["id"]: s for s in SECTORS}
    out.update(_custom)
    return out


def set_custom(docs):
    """Merge admin-defined sectors from Mongo (overrides built-ins with the same id)."""
    global _custom
    _custom = {d["id"]: d for d in docs if d.get("id") and d.get("name")}
    _RX.clear()


def sector(sid):
    return _all().get(sid) or _all()["tech"]


def sectors():
    return list(_all().values())


def _rx(s):
    if s["id"] not in _RX:
        roles = "|".join(re.escape(r.lower()) for r in s.get("roles", []))
        _RX[s["id"]] = re.compile(f"{s.get('kw') or '(?!x)x'}|{roles}", re.I)
    return _RX[s["id"]]


ORDER = ["data", "tech", "healthcare", "education", "legal", "finance", "hr", "support", "sales", "product", "design", "civil", "core_eng", "supply",
         "hospitality", "retail", "trades", "transport", "fashion", "science", "agri", "government", "freelance"]


def classify(title, text=""):
    """Best sector for a job title (falls back to the description head)."""
    title = title or ""
    ids = [i for i in ORDER if i in _all()] + [i for i in _all() if i not in ORDER]
    for src in (title, (text or "")[:600]):
        for sid in ids:
            if src and _rx(_all()[sid]).search(src):
                return sid
    return "other"


def weights(sid):
    return {**W_DEFAULT, **(_all().get(sid, {}).get("w") or {})}


def public(s, job_count=None):
    return {"id": s["id"], "name": s["name"], "roles": s.get("roles", []), "coding": bool(s.get("coding")),
            "oa_sections": [x["name"] for x in s.get("oa", [])], "oa_types": s.get("oa_types", ["Full OA"]),
            "styles": s.get("styles", ["Mixed", "Behavioral", "HR"]), "competencies": s.get("competencies", []), "note": s.get("note", ""),
            **({"job_count": job_count} if job_count is not None else {})}


# ---------------- explainable matching ----------------
LEVEL_YEARS = {"Entry": (0, 2), "Mid": (2, 6), "Senior": (5, 40)}
_YRS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?years?(?:'|’)?\s*(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience", re.I)
_MANDATORY = [
    ("Degree", re.compile(r"(bachelor'?s?|master'?s?|ph\.?d|degree|b\.?tech|b\.?e\.|mba|diploma)[^.]{0,60}(required|mandatory|must)|(required|must have|mandatory)[^.]{0,60}(bachelor|master|degree|diploma)", re.I)),
    ("License / registration", re.compile(r"licen[cs]e[ds]?|registered nurse|board certified|registration with|\bcdl\b|driving licen[cs]e", re.I)),
    ("Certification", re.compile(r"certif(ied|ication)[^.]{0,50}(required|mandatory|must)|(required|must)[^.]{0,40}certif", re.I)),
    ("Work authorisation", re.compile(r"(work|employment) (authori[sz]ation|permit|visa)|right to work|citizenship|security clearance", re.I)),
]
GENERIC = {"engineer", "developer", "intern", "junior", "senior", "lead", "associate", "development", "specialist", "trainee", "staff",
           "principal", "level", "entry", "graduate", "analyst", "manager", "consultant", "executive", "officer", "assistant", "head"}


def ctx_from(resume, profile):
    resume, profile = resume or {}, profile or {}
    skills = {s.lower() for s in (resume.get("skills") or []) + (profile.get("skills") or [])}
    roles = (profile.get("target_roles") or []) + (resume.get("recommended_roles") or [])
    secs = list(dict.fromkeys((profile.get("target_sectors") or []) + (resume.get("job_families") or [])))
    years = profile.get("years_experience")
    if years in (None, ""):
        years = resume.get("years_experience")
    return {"skills": skills, "roles": roles, "sectors": secs, "years": years, "work": profile.get("work_preference") or "Any",
            "locations": [l.lower() for l in profile.get("locations") or []], "has_data": bool(skills or roles or secs)}


def _role_fit(roles, title):
    t = title.lower()
    best = 0.0
    for r in roles:
        words = [w for w in re.findall(r"[a-z+#./-]+", r.lower()) if len(w) > 2 and w not in GENERIC]
        if not words:
            continue
        hit = sum(1 for w in words if w in t) / len(words)
        best = max(best, 1.0 if r.lower() in t else hit)
    return best


def _exp_fit(years, level):
    if years in (None, ""):
        return None
    lo, hi = LEVEL_YEARS.get(level or "Mid", (0, 40))
    y = float(years)
    return 1.0 if lo <= y <= hi + 2 else 0.6 if y > hi else max(0.0, 1 - (lo - y) / 3)


def _loc_fit(c, job):
    w = c["work"]
    wt = job.get("work_type", "")
    ok_work = w == "Any" or w == wt or (w == "Remote" and wt == "Remote")
    loc = (job.get("location") or "").lower()
    ok_loc = not c["locations"] or wt == "Remote" or any(l in loc for l in c["locations"])
    return 1.0 if ok_work and ok_loc else 0.5 if ok_work or ok_loc else 0.15


def quick_score(c, job):
    """Fast score for lists (no description parsing). None when the user has no profile data."""
    if not c["has_data"]:
        return None
    sid = job.get("sector") or "other"
    w = weights(sid)
    js = {s.lower() for s in job.get("skills", [])}
    f = {"skills": (len(js & c["skills"]) / max(len(js), 4)) if js else 0.35,
         "role": _role_fit(c["roles"], job.get("title", "")),
         "sector": 1.0 if sid in c["sectors"] else 0.4 if not c["sectors"] else 0.0,
         "experience": _exp_fit(c["years"], job.get("level")),
         "location": _loc_fit(c, job)}
    f["experience"] = 0.6 if f["experience"] is None else f["experience"]
    return int(min(97, round(sum(w[k] * f[k] for k in w) / sum(w.values()) * 100)))


def explain(c, job):
    sid = job.get("sector") or "other"
    w = weights(sid)
    js = [s for s in job.get("skills", [])]
    have = [s for s in js if s.lower() in c["skills"]]
    missing = [s for s in js if s.lower() not in c["skills"]]
    desc = job.get("description") or ""
    exp_f = _exp_fit(c["years"], job.get("level"))
    factors = [
        {"key": "skills", "label": "Skill match", "weight": w["skills"], "fit": (len(have) / max(len(js), 4)) if js else None,
         "detail": f"{len(have)} of {len(js)} listed skills" if js else "This listing names no specific skills"},
        {"key": "role", "label": "Role / title fit", "weight": w["role"], "fit": _role_fit(c["roles"], job.get("title", "")), "detail": "Compared with your target and recommended roles"},
        {"key": "sector", "label": "Industry fit", "weight": w["sector"], "fit": 1.0 if sid in c["sectors"] else 0.0 if c["sectors"] else None,
         "detail": f"Job sector: {sector(sid)['name'] if sid in _all() else 'Other'}"},
        {"key": "experience", "label": "Experience & seniority", "weight": w["experience"], "fit": exp_f,
         "detail": f"Job level {job.get('level', '?')}; your experience {c['years'] if c['years'] not in (None, '') else 'not provided'} years"},
        {"key": "location", "label": "Location & work type", "weight": w["location"], "fit": _loc_fit(c, job), "detail": f"{job.get('work_type', '')} · {job.get('location', '')}"},
    ]
    req, unmet = [], []
    m = _YRS.search(desc)
    if m:
        need = int(m.group(1))
        status = "unknown" if c["years"] in (None, "") else "met" if float(c["years"]) >= need else "unmet"
        req.append({"label": f"{need}+ years of experience", "status": status})
        if status == "unmet":
            unmet.append(req[-1]["label"])
    for label, rx in _MANDATORY:
        mm = rx.search(desc)
        if mm:
            req.append({"label": label, "status": "unknown", "evidence": desc[max(0, mm.start() - 40):mm.end() + 40].strip()})
    known = [f for f in factors if f["fit"] is not None]
    score = round(sum(f["weight"] * f["fit"] for f in known) / max(1, sum(f["weight"] for f in known)) * 100) if c["has_data"] else None
    if score is not None and unmet:
        score = min(score, 45)
    eligibility = ("Not eligible yet: " + ", ".join(unmet)) if unmet else ("Needs confirmation" if any(r["status"] == "unknown" for r in req) else "No mandatory requirement detected")
    return {"score": score, "factors": factors, "have": have, "missing": missing, "requirements": req, "eligibility": eligibility,
            "unverified": [r["label"] for r in req if r["status"] == "unknown"], "sector": sid}
