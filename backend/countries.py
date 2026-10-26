import re

REMOTE_ANY = "Remote / Anywhere"

COUNTRIES = {
    "United States": ["united states", "usa", "indiana", "indianapolis", "u.s.a", "u.s.", r"\bus\b", "new york", "san francisco", "seattle",
                      "austin", "boston", "chicago", "los angeles", "denver", "atlanta", "washington", "california", "texas",
                      "colorado", "massachusetts", "illinois", "florida", "virginia", "oregon", "georgia, us", "miami",
                      "palo alto", "mountain view", "menlo park", "sunnyvale", "san jose", "san mateo", "redwood city",
                      "kirkland", "bellevue", "pittsburgh", "philadelphia", "nyc", "sf bay", "bay area", "san diego",
                      "salt lake", "dallas", "houston", "phoenix", "minneapolis", "detroit", "raleigh", "nashville",
                      "portland", "brooklyn", "jersey city", "new jersey", "north carolina", "ohio", "michigan", "utah",
                      "arizona", "minnesota", "pennsylvania", "connecticut", "maryland", "tennessee", "wisconsin",
                      r",\s*(ca|ny|wa|tx|ma|co|il|fl|ga|va|or|nc|pa|nj|az|ut|mn|mi|oh|md|tn|ct|dc)\b"],
    "India": ["india", "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "delhi", "gurgaon", "gurugram", "noida",
              "chennai", "kolkata", "ahmedabad", "jaipur", "kochi", "trivandrum", "indore", "bhopal", "chandigarh"],
    "United Kingdom": ["united kingdom", r"\buk\b", "england", "scotland", "wales", "london", "manchester", "edinburgh",
                       "cambridge, uk", "bristol", "birmingham", "glasgow", "leeds", "great britain"],
    "Germany": ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne", "köln",
                "stuttgart", "düsseldorf", "dusseldorf", "dresden", "leipzig", "nuremberg", "nürnberg", "hannover", "bonn", "karlsruhe"],
    "Canada": ["canada", "toronto", "vancouver", "montreal", "montréal", "ottawa", "calgary", "waterloo", "edmonton", "ontario", "quebec", "british columbia"],
    "France": ["france", "paris", "lyon", "marseille", "toulouse", "bordeaux", "lille", "nantes"],
    "Netherlands": ["netherlands", "amsterdam", "rotterdam", "utrecht", "the hague", "eindhoven"],
    "Ireland": ["ireland", "dublin", "cork"],
    "Spain": ["spain", "madrid", "barcelona", "valencia", "seville"],
    "Portugal": ["portugal", "lisbon", "lisboa", "porto"],
    "Italy": ["italy", "milan", "milano", "rome", "turin", "torino"],
    "Poland": ["poland", "warsaw", "krakow", "kraków", "wroclaw", "wrocław", "gdansk"],
    "Switzerland": ["switzerland", "zurich", "zürich", "geneva", "basel", "lausanne"],
    "Austria": ["austria", "vienna", "wien", "graz"],
    "Belgium": ["belgium", "brussels", "antwerp", "ghent"],
    "Sweden": ["sweden", "stockholm", "gothenburg", "malmö", "malmo"],
    "Denmark": ["denmark", "copenhagen", "aarhus"],
    "Norway": ["norway", "oslo"],
    "Finland": ["finland", "helsinki"],
    "Czech Republic": ["czech", "prague", "brno"],
    "Romania": ["romania", "bucharest", "cluj"],
    "Hungary": ["hungary", "budapest"],
    "Greece": ["greece", "athens"],
    "Ukraine": ["ukraine", "kyiv", "kiev", "lviv"],
    "Estonia": ["estonia", "tallinn"],
    "Lithuania": ["lithuania", "vilnius"],
    "Turkey": ["turkey", "türkiye", "istanbul", "ankara"],
    "Israel": ["israel", "tel aviv", "jerusalem", "haifa"],
    "United Arab Emirates": ["united arab emirates", r"\buae\b", "dubai", "abu dhabi"],
    "Saudi Arabia": ["saudi", "riyadh", "jeddah"],
    "Egypt": ["egypt", "cairo"],
    "South Africa": ["south africa", "cape town", "johannesburg"],
    "Nigeria": ["nigeria", "lagos"],
    "Kenya": ["kenya", "nairobi"],
    "Singapore": ["singapore"],
    "Japan": ["japan", "tokyo", "osaka"],
    "South Korea": ["south korea", "korea", "seoul"],
    "China": ["china", "shanghai", "beijing", "shenzhen", "hangzhou"],
    "Hong Kong": ["hong kong"],
    "Taiwan": ["taiwan", "taipei"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide"],
    "New Zealand": ["new zealand", "auckland", "wellington"],
    "Philippines": ["philippines", "manila"],
    "Indonesia": ["indonesia", "jakarta"],
    "Malaysia": ["malaysia", "kuala lumpur"],
    "Vietnam": ["vietnam", "ho chi minh", "hanoi"],
    "Thailand": ["thailand", "bangkok"],
    "Pakistan": ["pakistan", "karachi", "lahore", "islamabad"],
    "Bangladesh": ["bangladesh", "dhaka"],
    "Sri Lanka": ["sri lanka", "colombo"],
    "Brazil": ["brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro"],
    "Mexico": ["mexico", "méxico", "guadalajara", "monterrey"],
    "Argentina": ["argentina", "buenos aires"],
    "Colombia": ["colombia", "bogota", "bogotá", "medellin", "medellín"],
    "Chile": ["chile", "santiago"],
    "Peru": ["peru", "lima"],
    "Costa Rica": ["costa rica", "san josé, costa rica"],
}

_RX = [(c, re.compile("|".join(p if p.startswith((r"\b", r",")) else rf"(?<!\w){re.escape(p)}(?!\w)" for p in pats), re.I))
       for c, pats in COUNTRIES.items()]
_ANY = re.compile(r"anywhere|worldwide|global|remote\s*$|^remote\b(?!.*\b(us|usa|uk|eu)\b)", re.I)


def detect_countries(location: str, work_type: str = "") -> list:
    loc = location or ""
    found = [c for c, rx in _RX if rx.search(loc)]
    if not found and work_type == "Remote" and (not loc or _ANY.search(loc) or loc.lower() in ("not specified", "remote")):
        return [REMOTE_ANY]
    if work_type == "Remote" and re.search(r"anywhere|worldwide|global", loc, re.I):
        found.append(REMOTE_ANY)
    return found[:12]
