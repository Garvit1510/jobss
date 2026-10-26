"""Author Accenture M1 directly (Emergent agent-written content, NO Gemini calls) and save through the existing validation."""
import asyncio
import os
import subprocess
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
import accenture_mocks as am  # noqa: E402
from routes_oa_builder import _valid_sql, _valid_web  # noqa: E402
from database import db  # noqa: E402

AUTHOR = "emergent_agent"
L = am.LIKERT

BEH = [  # (statement, trait, reverse_scored)
    ("I plan my tasks for the week before I start working on them.", "conscientiousness", False),
    ("I double-check my work for errors before submitting it.", "conscientiousness", False),
    ("I often leave tasks until the last moment.", "conscientiousness", True),
    ("I keep track of deadlines without needing reminders.", "conscientiousness", False),
    ("I find it hard to stay organised when I have several tasks at once.", "conscientiousness", True),
    ("I complete what I commit to, even when the work becomes tedious.", "conscientiousness", False),
    ("I enjoy working with people whose backgrounds differ from mine.", "teamwork", False),
    ("I share useful information with teammates without being asked.", "teamwork", False),
    ("I prefer to finish my own work rather than help a struggling teammate.", "teamwork", True),
    ("I value team success more than individual recognition.", "teamwork", False),
    ("I find group discussions a waste of time.", "teamwork", True),
    ("I adjust my working style to suit the people I work with.", "teamwork", False),
    ("I stay calm when project priorities change suddenly.", "adaptability", False),
    ("I feel uncomfortable when I have to work in an unfamiliar way.", "adaptability", True),
    ("I can switch between different types of tasks without losing focus.", "adaptability", False),
    ("I see changes in plans as an opportunity to improve.", "adaptability", False),
    ("I prefer routines that never change.", "adaptability", True),
    ("I can work effectively even when instructions are incomplete.", "adaptability", False),
    ("I admit my mistakes openly, even when no one would notice them.", "integrity", False),
    ("I follow company policies even when they slow me down.", "integrity", False),
    ("Bending a rule is acceptable if it helps meet a deadline.", "integrity", True),
    ("I give credit to colleagues for their contributions.", "integrity", False),
    ("I would keep quiet about a colleague's misconduct to avoid conflict.", "integrity", True),
    ("I protect confidential information even outside the workplace.", "integrity", False),
    ("I actively look for opportunities to learn new technologies.", "learning_agility", False),
    ("I ask for feedback so that I can improve my work.", "learning_agility", False),
    ("I avoid tasks that require skills I have not used before.", "learning_agility", True),
    ("I can quickly apply what I learn to real work problems.", "learning_agility", False),
    ("I rarely reflect on what went wrong after a task is finished.", "learning_agility", True),
    ("I enjoy figuring out how unfamiliar tools work.", "learning_agility", False),
    ("I recover quickly after a setback at work.", "resilience", False),
    ("Criticism of my work discourages me for a long time.", "resilience", True),
    ("I stay focused on solutions when a problem seems difficult.", "resilience", False),
    ("I can keep performing well under tight deadlines.", "resilience", False),
    ("I tend to give up when my first approach does not work.", "resilience", True),
    ("I keep a positive attitude during long, demanding projects.", "resilience", False),
    ("I try to understand the business goal behind every client request.", "client_focus", False),
    ("I keep clients informed about progress, including bad news.", "client_focus", False),
    ("Client satisfaction is mainly the responsibility of senior staff, not mine.", "client_focus", True),
    ("I follow up after delivering work to confirm it meets the need.", "client_focus", False),
    ("I find it frustrating when clients change their requirements.", "client_focus", True),
    ("I look for ways to deliver more value than the client expected.", "client_focus", False),
    ("I take the initiative when a team lacks direction.", "leadership", False),
    ("I am comfortable making decisions with limited information.", "leadership", False),
    ("I prefer others to take responsibility for group decisions.", "leadership", True),
    ("I motivate others when the team's morale is low.", "leadership", False),
    ("I hesitate to voice my opinion in meetings with senior colleagues.", "leadership", True),
    ("I help new team members settle in and learn quickly.", "leadership", False),
    ("I set clear goals for myself and measure my progress.", "conscientiousness", False),
    ("I remain respectful when I disagree with a teammate.", "teamwork", False),
]

# pseudocode questions carry a python `check` that must evaluate to the correct option text
PSEUDO = [
    ("What will be the output of the following pseudocode?\n\nInteger a = 5, b = 3, c = 0\nfor (each i from 1 to 4)\n    if ((a + i) mod 2 == 0)\n        c = c + b\n    else\n        c = c - 1\n    end if\nend for\nPrint c",
     ["4", "5", "2", "8"], "c=0\nfor i in range(1,5):\n    c = c+3 if (5+i)%2==0 else c-1\nr=c",
     "i=1: 6 even, c=3; i=2: 7 odd, c=2; i=3: 8 even, c=5; i=4: 9 odd, c=4."),
    ("What will be the output of the following pseudocode?\n\nInteger x = 10, y = 4\nwhile (x > y)\n    x = x - y\n    y = y + 1\nend while\nPrint x + y",
     ["11", "7", "6", "9"], "x,y=10,4\nwhile x>y:\n    x-=y; y+=1\nr=x+y", "(10,4) -> (6,5) -> (1,6); loop stops, 1 + 6 = 7."),
    ("What will be the output of the following pseudocode?\n\nFunction fun(Integer n)\n    if (n <= 1)\n        return 1\n    end if\n    return n * fun(n - 2)\nEnd Function\n\nPrint fun(7)",
     ["5040", "35", "105", "15"], "f=lambda n: 1 if n<=1 else n*f(n-2)\nr=f(7)", "fun(7) = 7 x 5 x 3 x fun(1) = 105."),
    ("What will be the output of the following pseudocode? (& is bitwise AND, ^ is bitwise XOR)\n\nInteger p = 12, q = 10\nPrint (p & q) + (p ^ q)",
     ["8", "22", "6", "14"], "r=(12&10)+(12^10)", "12 = 1100, 10 = 1010. AND = 1000 (8), XOR = 0110 (6); 8 + 6 = 14."),
    ("What will be the output of the following pseudocode?\n\nInteger arr[5] = {3, 8, 1, 9, 4}\nInteger s = 0\nfor (i = 0 to 4)\n    if (arr[i] > arr[(i + 1) mod 5])\n        s = s + arr[i]\n    end if\nend for\nPrint s",
     ["21", "17", "25", "12"], "a=[3,8,1,9,4]\nr=sum(a[i] for i in range(5) if a[i]>a[(i+1)%5])", "8 > 1, 9 > 4 and 4 > 3 (wrap-around) qualify: 8 + 9 + 4 = 21."),
    ("What will be the output of the following pseudocode?\n\nInteger count = 0\nfor (i = 1 to 4)\n    for (j = i to 4)\n        count = count + 1\n    end for\nend for\nPrint count",
     ["16", "6", "10", "4"], "r=sum(1 for i in range(1,5) for j in range(i,5))", "Inner loop runs 4 + 3 + 2 + 1 = 10 times."),
    ("What will be the output of the following pseudocode? (/ is integer division)\n\nInteger n = 2345, r = 0\nwhile (n > 0)\n    r = r * 10 + (n mod 10)\n    n = n / 10\nend while\nPrint r mod 7",
     ["6", "0", "3", "5"], "n,r=2345,0\nwhile n>0:\n    r=r*10+n%10; n//=10\nr=r%7", "The loop reverses the digits: r = 5432, and 5432 = 7 x 776, so r mod 7 = 0."),
    ("What will be the output of the following pseudocode?\n\nInteger a = 1, b = 1, t\nfor (k = 1 to 5)\n    t = a + b\n    a = b\n    b = t\nend for\nPrint b",
     ["8", "21", "5", "13"], "a=b=1\nfor _ in range(5):\n    a,b=b,a+b\nr=b", "b takes the values 2, 3, 5, 8, 13 - the Fibonacci sequence."),
]

MCQ = [  # (category, topic, question, options, answer_index, explanation, oop_language, run_check)
    ("ms_office", "MS Excel", "In MS Excel, which function returns the number of non-empty cells in the range A1:A20, counting text as well as numbers?",
     ["COUNT", "COUNTA", "COUNTBLANK", "SUM"], 1, "COUNTA counts every non-empty cell; COUNT counts only numeric cells and COUNTBLANK counts empty ones.", None, None),
    ("ms_office", "MS Excel", "Cell B2 contains the formula =$A$1+A2. If the formula is copied from B2 to C3, what will C3 contain?",
     ["=$A$1+B3", "=$B$2+B3", "=$A$1+A2", "=$A$1+B2"], 0, "$A$1 is an absolute reference and does not change; A2 is relative and shifts one column right and one row down to B3.", None, None),
    ("ms_office", "MS Word", "Assume that you are preparing a 60-page project report in MS Word and need a table of contents that updates automatically. What should you do first?",
     ["Insert bookmarks at every page break", "Apply the built-in Heading styles to the section titles", "Place each section title in a text box", "Turn on Track Changes"], 1,
     "Word builds an automatic table of contents from paragraphs formatted with Heading styles.", None, None),
    ("ms_office", "MS PowerPoint", "Consider that your company logo must appear in the same position on every slide of a 40-slide presentation. What is the most efficient approach?",
     ["Copy and paste the logo onto each slide", "Use the Animation Painter", "Insert the logo on the Slide Master", "Insert the logo as the background of the first slide"], 2,
     "Objects placed on the Slide Master appear on every slide that uses its layouts, and a single edit updates them all.", None, None),
    ("ms_office", "MS Excel", "An HR executive has a table where employee IDs are in the leftmost column and salaries are in the fourth column. Which function is best suited to fetch an employee's salary by ID?",
     ["HLOOKUP", "VLOOKUP", "MATCH", "CONCAT"], 1, "VLOOKUP searches the first column of a table vertically and returns a value from a given column; MATCH only returns a position.", None, None),
    ("cloud", "Serverless", "Assume that a startup wants to run code in response to events without provisioning or patching servers, paying only for each execution. Which option fits best?",
     ["Infrastructure as a Service (IaaS)", "On-premise virtualisation", "Serverless computing (Function as a Service)", "Colocation hosting"], 2,
     "FaaS runs code on demand, scales automatically and bills per execution with no server management.", None, None),
    ("cloud", "Service models", "Which cloud service model gives the customer control over the operating system and runtime, but not the physical hardware?",
     ["SaaS", "PaaS", "IaaS", "FaaS"], 2, "In IaaS the provider manages the physical infrastructure while the customer manages the OS, runtime and applications.", None, None),
    ("cloud", "Elasticity", "Consider an e-commerce site whose cloud setup automatically adds servers during a festive sale and removes them afterwards. Which cloud characteristic is this?",
     ["Elasticity", "Multi-tenancy", "Data residency", "Vendor lock-in"], 0, "Elasticity is the automatic provisioning and release of resources in line with demand.", None, None),
    ("cloud", "Deployment models", "An organisation keeps sensitive customer data in its own private data centre but uses a public cloud for extra compute during peak loads. Which deployment model is this?",
     ["Public cloud", "Private cloud", "Community cloud", "Hybrid cloud"], 3, "Combining private infrastructure with public cloud resources is a hybrid cloud.", None, None),
    ("cloud", "Shared responsibility", "Under the shared responsibility model for IaaS, who is responsible for applying security patches to the guest operating system of a virtual machine?",
     ["The cloud provider", "The customer", "Both equally, by default", "The internet service provider"], 1,
     "In IaaS the provider secures the physical hosts and hypervisor; the guest OS and everything above it are the customer's responsibility.", None, None),
    ("networks", "OSI model", "Which layer of the OSI model is responsible for routing packets between different networks?",
     ["Data link layer", "Network layer", "Transport layer", "Session layer"], 1, "The network layer (layer 3) handles logical addressing and routing, e.g. IP.", None, None),
    ("networks", "Protocols", "Which protocol is used on an IPv4 LAN to find the MAC address that corresponds to a known IP address?",
     ["DNS", "DHCP", "ARP", "ICMP"], 2, "ARP resolves IPv4 addresses to MAC addresses; DNS resolves names to IPs and DHCP assigns addresses.", None, None),
    ("networks", "Subnetting", "How many usable host addresses are available in a /26 IPv4 subnet?",
     ["64", "62", "30", "126"], 1, "A /26 leaves 6 host bits: 2^6 = 64 addresses, minus the network and broadcast addresses = 62.", None, None),
    ("networks", "Devices", "Which device forwards frames within a LAN based on destination MAC addresses?",
     ["Hub", "Switch", "Router", "Repeater"], 1, "A switch learns MAC addresses and forwards frames only to the right port; a hub floods every port and a router works with IP addresses.", None, None),
    ("networks", "Transport protocols", "Assume that a live video-conferencing application must keep latency low and can tolerate occasional packet loss. Which transport protocol is most suitable?",
     ["TCP", "UDP", "FTP", "SMTP"], 1, "UDP has no retransmission or connection overhead, so it suits real-time media; FTP and SMTP are application-layer protocols.", None, None),
    ("networks", "Ports", "Which port does HTTPS use by default?",
     ["80", "21", "443", "25"], 2, "HTTPS uses TCP port 443; 80 is HTTP, 21 is FTP and 25 is SMTP.", None, None),
    ("cybersecurity", "Social engineering", "An employee receives an email that appears to come from the IT department, asking them to verify their password through a link. Which attack is this most likely to be?",
     ["Phishing", "Distributed denial of service", "SQL injection", "Brute-force attack"], 0, "A deceptive email that tricks the user into revealing credentials is phishing.", None, None),
    ("cybersecurity", "Application security", "Assume that an attacker types ' OR '1'='1 into a login form and gains access. What is the most effective defence against this attack?",
     ["Using parameterised queries (prepared statements)", "Increasing the minimum password length", "Serving the site over HTTP instead of HTTPS", "Disabling the firewall"], 0,
     "This is SQL injection; parameterised queries keep user input as data so it cannot change the SQL statement.", None, None),
    ("cybersecurity", "Authentication", "A banking app asks for a password and then a one-time code sent to the user's registered phone. Which security mechanism is this?",
     ["Single sign-on", "Multi-factor authentication", "Role-based access control", "Biometric-only authentication"], 1,
     "Combining something you know (password) with something you have (phone) is multi-factor authentication.", None, None),
    ("cybersecurity", "Password storage", "What is the most secure way for an application to store user passwords?",
     ["In plain text in an access-restricted database", "Encrypted with a reversible key stored in the source code", "Hashed with a salted, slow algorithm such as bcrypt", "Encoded in Base64"], 2,
     "Salted slow hashes cannot be reversed and resist rainbow-table and brute-force attacks; Base64 is only an encoding.", None, None),
    ("cybersecurity", "Malware", "Consider malware that encrypts the files on a company's servers and demands payment for the decryption key. Which type of malware is it?",
     ["Spyware", "Adware", "Ransomware", "Rootkit"], 2, "Ransomware encrypts victims' data and demands a ransom for its release.", None, None),
    ("oop", "Polymorphism (Java)", "What is the output of the following Java code, and which concept does it demonstrate?\n\nclass A { void show() { System.out.print(\"A\"); } }\nclass B extends A { void show() { System.out.print(\"B\"); } }\npublic class Main {\n    public static void main(String[] args) {\n        A obj = new B();\n        obj.show();\n    }\n}",
     ["A - method overloading", "B - method overriding (runtime polymorphism)", "AB - multiple inheritance", "Compilation error"], 1,
     "The reference type is A but the object is B, so the overridden B.show() is chosen at runtime (dynamic dispatch).", "java", None),
    ("oop", "Encapsulation (Java)", "In Java, which access modifier makes a class member accessible only within its own class?",
     ["public", "protected", "default (package-private)", "private"], 3, "private restricts access to the declaring class, which is the basis of encapsulation.", "java", None),
    ("oop", "Class attributes (Python)", "What is the output of the following Python code?\n\nclass Counter:\n    count = 0\n    def __init__(self):\n        Counter.count += 1\n\na = Counter(); b = Counter(); c = Counter()\nprint(a.count)",
     ["1", "3", "0", "AttributeError"], 1, "count is a class attribute shared by all instances; it is incremented on each of the three constructions.",
     "python", ("python", "class Counter:\n    count = 0\n    def __init__(self):\n        Counter.count += 1\na = Counter(); b = Counter(); c = Counter()\nprint(a.count)")),
    ("oop", "Inheritance (Python)", "What is the output of the following Python code?\n\nclass Animal:\n    def speak(self):\n        return \"...\"\n\nclass Dog(Animal):\n    def speak(self):\n        return \"Woof \" + super().speak()\n\nprint(Dog().speak())",
     ["Woof ...", "Woof Woof", "...", "AttributeError"], 0, "Dog overrides speak() and uses super() to call the parent implementation, concatenating the two strings.",
     "python", ("python", "class Animal:\n    def speak(self):\n        return '...'\nclass Dog(Animal):\n    def speak(self):\n        return 'Woof ' + super().speak()\nprint(Dog().speak())")),
    ("oop", "Polymorphism (JavaScript)", "What is the output of the following JavaScript code?\n\nclass Shape { area() { return 0; } }\nclass Square extends Shape {\n  constructor(s) { super(); this.s = s; }\n  area() { return this.s * this.s; }\n}\nconst shapes = [new Shape(), new Square(3)];\nconsole.log(shapes.map(x => x.area()).join(\",\"));",
     ["0,9", "0,0", "9,9", "TypeError"], 0, "Each object uses its own area(): Shape returns 0 and Square overrides it to return 9.",
     "javascript", ("javascript", "class Shape { area() { return 0; } }\nclass Square extends Shape { constructor(s) { super(); this.s = s; } area() { return this.s * this.s; } }\nconst shapes = [new Shape(), new Square(3)];\nconsole.log(shapes.map(x => x.area()).join(','));")),
    ("oop", "Encapsulation (JavaScript)", "What is the output of the following JavaScript code?\n\nclass Account {\n  #balance = 100;\n  deposit(x) { this.#balance += x; return this.#balance; }\n}\nconst acc = new Account();\nconsole.log(acc.deposit(50), acc.balance);",
     ["150 undefined", "150 150", "SyntaxError", "100 undefined"], 0, "#balance is a private field: deposit() can update it, but acc.balance is a different, undefined public property.",
     "javascript", ("javascript", "class Account { #balance = 100; deposit(x) { this.#balance += x; return this.#balance; } }\nconst acc = new Account();\nconsole.log(acc.deposit(50), acc.balance);")),
    ("cs_fundamentals", "Algorithms", "What is the worst-case time complexity of binary search on a sorted array of n elements?",
     ["O(n)", "O(log n)", "O(n log n)", "O(1)"], 1, "Each comparison halves the search space, so at most about log2(n) steps are needed.", None, None),
    ("cs_fundamentals", "Data structures", "Which data structure does a program's runtime use to manage function calls and recursion?",
     ["Queue", "Stack", "Heap", "Hash table"], 1, "Each call pushes a frame onto the call stack and returning pops it (LIFO).", None, None),
    ("cs_fundamentals", "DBMS", "Which normal form removes partial dependencies of non-key attributes on part of a composite primary key?",
     ["1NF", "2NF", "3NF", "BCNF"], 1, "2NF requires every non-key attribute to depend on the whole composite key; 3NF then removes transitive dependencies.", None, None),
    ("cs_fundamentals", "Operating systems", "Which of the following is NOT one of the four necessary conditions for a deadlock?",
     ["Mutual exclusion", "Hold and wait", "Preemption", "Circular wait"], 2,
     "The Coffman conditions are mutual exclusion, hold and wait, NO preemption and circular wait; allowing preemption prevents deadlock.", None, None),
    ("sjt", "Ownership", "You are two days away from a client deadline when you find a defect in a module built by a teammate who is on leave. What is the most effective response?",
     ["Ignore it, because the module is not yours", "Inform your lead immediately with an impact assessment and a proposed fix, then fix it as agreed",
      "Quietly rewrite the module overnight without telling anyone", "Tell the client directly that the deadline will be missed"], 1,
     "Best: it surfaces the risk early, owns the problem and keeps the lead in the decision. Ignoring it lets the defect reach the client; a silent rewrite bypasses review and can break other work; telling the client the deadline will be missed is premature and skips the team.", None, None),
    ("sjt", "Scope management", "During a call, a client informally asks you to add a feature that is outside the agreed project scope. What is the most effective response?",
     ["Agree immediately and start building it to keep the client happy", "Refuse flatly because it is out of scope", "Ignore the request and hope the client forgets",
      "Acknowledge the request, capture the details and take it through the change-request process with your manager before committing"], 3,
     "Best: it respects the client and the contract while letting effort and cost be assessed. Agreeing immediately risks unplanned work; a flat refusal damages the relationship; ignoring it breaks trust.", None, None),
    ("sjt", "Learning agility", "Your project needs a technology you have never used, and no formal training is scheduled for weeks. What is the most effective response?",
     ["Start learning it right away from documentation and internal resources, pair with an experienced colleague, and tell your lead how long you need to ramp up",
      "Wait for the formal training before starting any related task", "Ask to be moved to a different project", "Pretend you already know it and learn by trial and error on client code"], 0,
     "Best: it shows initiative while managing expectations. Waiting delays the project; asking to move avoids growth; pretending puts client code at risk.", None, None),
    ("sjt", "Team conflict", "A teammate keeps missing stand-ups and their delayed tasks are now blocking your work. What is the most effective first step?",
     ["Complain about them in the team chat", "Do their tasks yourself without saying anything",
      "Talk to them privately to understand the issue and offer help, and involve the lead if it continues", "Report them to HR immediately"], 2,
     "Best: a private, supportive conversation addresses the cause and escalates proportionately if needed. Public complaints harm the team; silently doing their work hides the problem; going to HR first is disproportionate.", None, None),
    ("sjt", "Integrity", "You notice a colleague copying confidential client data to a personal cloud drive. What is the most effective response?",
     ["Ignore it, because it is not your responsibility", "Confront the colleague loudly in front of the team",
      "Copy the data to your own device as evidence", "Report it through the proper channel, such as your manager or the information-security team, as company policy requires"], 3,
     "Best: data-protection incidents must go through the defined reporting channel quickly. Ignoring it allows a breach; public confrontation is unprofessional; copying the data is itself a breach.", None, None),
]

DSA = {"title": "Exact Load Segments", "difficulty": "medium", "topic": "Arrays / prefix sums",
       "problem": "A logistics company records the weights of N parcels in the order they arrive on a conveyor belt. A delivery truck can only be loaded with a "
                  "contiguous segment of parcels, and the dispatcher wants segments whose total weight is exactly K.\n\nCount the number of contiguous segments "
                  "(subarrays) whose sum is exactly K. Weights can be negative because returned parcels are recorded as negative values.",
       "input_format": "First line: two integers N and K.\nSecond line: N space-separated integers, the weights.",
       "output_format": "A single integer: the number of contiguous segments with sum exactly K.",
       "constraints": "1 <= N <= 10^5\n-10^4 <= weight <= 10^4\n-10^9 <= K <= 10^9",
       "samples": [{"input": "5 5\n1 2 3 2 3", "output": "3", "explanation": "Segments [2,3], [3,2] and [2,3] each sum to 5."},
                   {"input": "4 0\n0 0 0 0", "output": "10", "explanation": "Every one of the 4*5/2 = 10 segments sums to 0."}],
       "hidden_inputs": ["1 7\n7", "1 3\n5", "6 3\n1 -1 3 0 2 1", "5 -2\n-1 -1 2 -2 0", "8 10\n10 0 0 10 -10 10 5 5",
                         "10 4\n1 3 1 3 1 3 1 3 1 3", "3 1000000000\n10000 10000 10000", "7 0\n1 -1 1 -1 1 -1 1"],
       "reference_python": "import sys\nfrom collections import defaultdict\n\ndef main():\n    d = sys.stdin.read().split()\n    n, k = int(d[0]), int(d[1])\n"
                           "    a = list(map(int, d[2:2 + n]))\n    seen = defaultdict(int)\n    seen[0] = 1\n    s = res = 0\n    for x in a:\n        s += x\n"
                           "        res += seen[s - k]\n        seen[s] += 1\n    print(res)\n\nmain()\n"}

SQL = {"title": "Top Salary per Large Department", "difficulty": "medium",
       "problem": "The HR team needs, for every department that has at least 2 employees, the department name and the highest salary in that department.\n"
                  "Return columns dept_name, max_salary. Order by max_salary descending, then dept_name ascending.",
       "schema": "CREATE TABLE departments (id INT PRIMARY KEY, name VARCHAR(50));\nCREATE TABLE employees (id INT PRIMARY KEY, name VARCHAR(50), dept_id INT, salary DECIMAL(10,2));",
       "datasets": [
           "INSERT INTO departments VALUES (1,'Engineering'),(2,'Sales'),(3,'HR'),(4,'Finance');\n"
           "INSERT INTO employees VALUES (1,'Asha',1,90000),(2,'Ravi',1,75000),(3,'Meera',2,60000),(4,'John',2,65000),(5,'Kiran',3,50000),(6,'Neha',4,82000),(7,'Arjun',4,82000);",
           "INSERT INTO departments VALUES (1,'Alpha'),(2,'Beta'),(3,'Gamma'),(4,'Delta');\n"
           "INSERT INTO employees VALUES (1,'A',1,50000),(2,'B',1,NULL),(3,'C',2,70000),(4,'D',2,70000),(5,'E',3,70000),(6,'F',3,30000),(7,'G',NULL,99000),(8,'H',4,99000);",
           "INSERT INTO departments VALUES (1,'Ops'),(2,'Legal'),(3,'Design'),(4,'Support'),(5,'Data');\n"
           "INSERT INTO employees VALUES (1,'e1',1,40000),(2,'e2',1,42000),(3,'e3',1,41000),(4,'e4',2,90000),(5,'e5',3,55000),(6,'e6',3,58000),(7,'e7',4,30000),"
           "(8,'e8',4,31000),(9,'e9',4,29000),(10,'e10',4,33000),(11,'e11',5,58000),(12,'e12',5,57000),(13,'e13',5,20000),(14,'e14',2,10000),(15,'e15',3,58000),(16,'e16',1,39000);"],
       "reference": "SELECT d.name AS dept_name, MAX(e.salary) AS max_salary FROM departments d JOIN employees e ON e.dept_id = d.id "
                    "GROUP BY d.id, d.name HAVING COUNT(e.id) >= 2 ORDER BY max_salary DESC, dept_name ASC;",
       "ordered": True}

WEB = {"title": "Message Character Counter", "difficulty": "easy",
       "problem": "Build a message box with a live character counter.\n- A textarea with id \"msg\".\n- A span with id \"count\" showing \"<n>/50\" where n is the number of characters typed (\"0/50\" initially).\n"
                  "- A button with id \"send\" that is disabled when the message is empty or longer than 50 characters.\n- When the message is longer than 50 characters, add the class \"over\" to #count; remove it otherwise.",
       "starter": {"html": "<textarea id=\"msg\"></textarea>\n<span id=\"count\"></span>\n<button id=\"send\">Send</button>", "css": "", "js": "// your code here\n"},
       "reference": {"html": "<textarea id=\"msg\"></textarea>\n<span id=\"count\">0/50</span>\n<button id=\"send\" disabled>Send</button>", "css": ".over { color: red; }",
                     "js": "const msg = document.getElementById('msg'), count = document.getElementById('count'), send = document.getElementById('send');\n"
                           "function update() { const n = msg.value.length; count.textContent = n + '/50'; count.classList.toggle('over', n > 50); send.disabled = n === 0 || n > 50; }\n"
                           "msg.addEventListener('input', update);\nupdate();\n"},
       "tests": [
           {"name": "Initial counter", "why": "Counter starts at 0/50", "script": "return document.getElementById('count').textContent.trim() === '0/50';"},
           {"name": "Disabled when empty", "why": "Send disabled for empty message", "script": "return document.getElementById('send').disabled === true;"},
           {"name": "Counts typed text", "why": "Counter updates on input", "script": "const m = document.getElementById('msg'); m.value = 'hello'; m.dispatchEvent(new window.Event('input', {bubbles: true})); await new Promise(r => setTimeout(r, 50)); return document.getElementById('count').textContent.trim() === '5/50';"},
           {"name": "Enabled for valid text", "why": "Send enabled for 1-50 chars", "script": "const m = document.getElementById('msg'); m.value = 'hi'; m.dispatchEvent(new window.Event('input', {bubbles: true})); await new Promise(r => setTimeout(r, 50)); return document.getElementById('send').disabled === false;"},
           {"name": "Over limit class", "why": "Adds class over above 50", "script": "const m = document.getElementById('msg'); m.value = 'x'.repeat(51); m.dispatchEvent(new window.Event('input', {bubbles: true})); await new Promise(r => setTimeout(r, 50)); return document.getElementById('count').classList.contains('over') && document.getElementById('count').textContent.trim() === '51/50';"},
           {"name": "Disabled over limit", "why": "Send disabled above 50", "script": "const m = document.getElementById('msg'); m.value = 'x'.repeat(60); m.dispatchEvent(new window.Event('input', {bubbles: true})); await new Promise(r => setTimeout(r, 50)); return document.getElementById('send').disabled === true;"},
           {"name": "Back under limit", "why": "Class removed at 50 chars", "script": "const m = document.getElementById('msg'); m.value = 'x'.repeat(60); m.dispatchEvent(new window.Event('input', {bubbles: true})); m.value = 'x'.repeat(50); m.dispatchEvent(new window.Event('input', {bubbles: true})); await new Promise(r => setTimeout(r, 50)); const c = document.getElementById('count'); return !c.classList.contains('over') && !document.getElementById('send').disabled;"}]}


def gen_meta():
    return {"origin": "generated", "generated_by": AUTHOR, "verified_official": False, "answer_key_source": "ai_generated",
            "key_status": "ai_derived_unverified", "review_required": True, "review": {"status": "pending"}}


def run(lang, code):
    cmd = ["python3", "-c", code] if lang == "python" else ["node", "-e", code]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()


async def main():
    lib = await db.acc_mock_libraries.find_one({"version": 1}, {"_id": 0})
    m1 = await db.acc_mocks.find_one({"library_id": lib["id"], "mock_id": "M1"}, {"_id": 0})
    old = m1.get("rounds") or {}
    src_q = [q for q in (old.get("technical") or {}).get("questions", []) if q.get("origin") == "source"]
    qs = list(src_q)
    for text, opts, check, exp in PSEUDO:
        ns = {}
        exec(check, ns)
        ai = opts.index(str(ns["r"]))
        qs.append({**gen_meta(), "question": text, "options": opts, "answer_index": ai, "explanation": exp, "category": "pseudocode",
                   "topic": "Pseudocode", "difficulty": "medium", "auto_check": "output verified by executing an equivalent program"})
    have = {k: sum(1 for q in qs if q["category"] == k) for k in am.TECH_CATEGORIES}
    for cat, topic, text, opts, ai, exp, lang, chk in MCQ:
        if have[cat] >= am.TECH_CATEGORIES[cat][1]:
            continue
        q = {**gen_meta(), "question": text, "options": opts, "answer_index": ai, "explanation": exp, "category": cat, "topic": topic, "difficulty": "medium"}
        if lang:
            q["oop_language"] = lang
        if chk:
            out = run(*chk)
            assert out == opts[ai], (text[:40], out, opts[ai])
            q["auto_check"] = "output verified by executing the code"
        have[cat] += 1
        qs.append(q)
    order = list(am.TECH_CATEGORIES)
    qs.sort(key=lambda q: order.index(q["category"]))
    for i, q in enumerate(qs):
        q["qid"] = f"M1-T{i + 1}"
    beh = [{"qid": f"M1-B{i + 1}", "statement": s, "trait": t, "reverse_scored": r, "options": L, "origin": "generated", "generated_by": AUTHOR,
            "verified_official": False} for i, (s, t, r) in enumerate(BEH)]
    dsa = await am.validate_dsa(DSA)
    sql = await _valid_sql(SQL)
    web = await _valid_web(WEB)
    print("dsa", bool(dsa), "sql", bool(sql), "web", bool(web) and len(web["tests"]))
    probs = []
    for p, t in ((dsa, "dsa"), (sql, "sql"), (web, "frontend_js")):
        if p:
            slot = next(x for x in am.CODING_SLOTS if x["type"] == t)
            probs.append({**p, "type": t, "origin": "generated", "generated_by": AUTHOR, "verified_official": False, "key_status": "reference_executed",
                          "qid": f"M1-C{slot['order']}", "order": slot["order"], "minutes": slot["minutes"]})
    rounds = {"behavioural": {"items": beh}, "gamified": {"activities": am._games(1)}, "technical": {"questions": qs}, "coding": {"problems": probs}}
    errs, warns, stats = am.validate_mock(rounds)
    unfinished = [n for n, pre in (("Round 1 Behavioural", "Behavioural:"), ("Round 2 Gamified", "Gamified:"), ("Round 3 Technical", "Technical:"),
                                   ("Round 4 Coding", "Coding:")) if any(e.startswith(pre) for e in errs)]
    status = "valid" if not errs else "incomplete"
    await db.acc_mocks.update_one({"library_id": lib["id"], "mock_id": "M1"}, {"$set": {
        "rounds": rounds, "status": status, "error": None, "generated_by": AUTHOR, "updated_at": am.now_iso(),
        "validation": {"errors": errs, "warnings": warns, "stats": stats, "validated_at": am.now_iso(), "unfinished_rounds": unfinished}}})
    await db.acc_mocks.update_many({"library_id": lib["id"], "status": "generating"}, {"$set": {"status": "pending"}})
    await db.acc_mock_libraries.update_one({"id": lib["id"]}, {"$set": {"status": "incomplete", "stage": "M1 authored by Emergent agent (no Gemini); M2-M40 deferred",
                                                                      "updated_at": am.now_iso()}})
    print("STATUS", status, "errors", errs)
    print("warnings", warns)
    print({k: v for k, v in stats.items() if k != "blocking"})
    print("counts", {k: len(list(v.values())[0]) for k, v in rounds.items()})


asyncio.run(main())
