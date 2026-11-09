"""Static reference data for the fictional asset manager "Aurora Peak Investments".

Everything here is invented for a portfolio project. Firm, fund, advisor and client
names are random combinations; any resemblance to real organisations is coincidental.
"""
from __future__ import annotations

FIRM_NAME = "Aurora Peak Investments"

# --------------------------------------------------------------------------------------
# Sales territories (8) and the states they cover. `weight` = share of advisors.
# --------------------------------------------------------------------------------------
TERRITORIES = [
    {"code": "NE", "name": "Northeast", "region": "East", "weight": 0.09,
     "states": ["ME", "NH", "VT", "MA", "RI", "CT"]},
    {"code": "NYM", "name": "New York Metro", "region": "East", "weight": 0.14,
     "states": ["NY", "NJ"]},
    {"code": "MA", "name": "Mid-Atlantic", "region": "East", "weight": 0.11,
     "states": ["PA", "DE", "MD", "DC", "VA", "WV"]},
    {"code": "SE", "name": "Southeast", "region": "South", "weight": 0.18,
     "states": ["NC", "SC", "GA", "FL", "AL", "TN", "MS", "KY"]},
    {"code": "MW", "name": "Midwest", "region": "Central", "weight": 0.15,
     "states": ["OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO"]},
    {"code": "SC", "name": "South Central", "region": "Central", "weight": 0.12,
     "states": ["TX", "OK", "AR", "LA", "KS", "NE"]},
    {"code": "MT", "name": "Mountain", "region": "West", "weight": 0.08,
     "states": ["CO", "UT", "AZ", "NM", "NV", "ID", "MT", "WY", "ND", "SD"]},
    {"code": "PC", "name": "Pacific", "region": "West", "weight": 0.13,
     "states": ["CA", "OR", "WA", "AK", "HI"]},
]

# --------------------------------------------------------------------------------------
# Intermediary channels. Firms in channels with vendor "A" report trades through the
# wirehouse/bank feed, vendor "B" through the independent/RIA feed (different formats).
# --------------------------------------------------------------------------------------
CHANNELS = {
    "Wirehouse":      {"firms": {"full": 4,  "small": 3},  "advisor_share": 0.28, "vendor": "A",
                       "etf_pref": 0.35, "mf_shelf": 0.88, "book_median": 180e6, "group": "WH"},
    "Regional BD":    {"firms": {"full": 12, "small": 4},  "advisor_share": 0.17, "vendor": "A",
                       "etf_pref": 0.30, "mf_shelf": 0.80, "book_median": 110e6, "group": "WH"},
    "Bank/Trust":     {"firms": {"full": 10, "small": 3},  "advisor_share": 0.10, "vendor": "A",
                       "etf_pref": 0.40, "mf_shelf": 0.72, "book_median": 90e6,  "group": "WH"},
    "Independent BD": {"firms": {"full": 26, "small": 6},  "advisor_share": 0.22, "vendor": "B",
                       "etf_pref": 0.45, "mf_shelf": 0.82, "book_median": 70e6,  "group": "IR"},
    "RIA":            {"firms": {"full": 66, "small": 12}, "advisor_share": 0.23, "vendor": "B",
                       "etf_pref": 0.78, "mf_shelf": 0.55, "book_median": 220e6, "group": "IR"},
}
CHANNEL_GROUPS = {"WH": "Wirehouse, Regional & Bank", "IR": "Independent & RIA"}

FIRM_SUFFIX = {
    "Wirehouse": ["Wealth Management"],
    "Regional BD": ["Securities", "Investment Services"],
    "Bank/Trust": ["Bank & Trust", "Trust Company"],
    "Independent BD": ["Financial Network", "Advisor Group"],
    "RIA": ["Capital Advisors", "Wealth Partners", "Private Wealth", "Family Office"],
}
NAME_STEMS = [
    "Alder", "Birchwood", "Cobalt", "Driftwood", "Elmstead", "Foxglove", "Granite Bay",
    "Harbor Point", "Ironleaf", "Juniper", "Kingsbridge", "Larkspur", "Maple Crest",
    "Northgate", "Oakhollow", "Pinehurst", "Quarry Hill", "Redfern", "Silverline",
    "Timberline", "Upland", "Valewood", "Westbrook", "Yarrow", "Zephyr", "Ashgrove",
    "Bluewater", "Cedar Run", "Dovecote", "Emberly", "Fairhollow", "Glenmoor", "Hawthorne",
    "Indigo", "Jasper Lane", "Kestrel Ridge", "Lumen", "Meadowlark", "Nettlefield",
    "Orchard Gate", "Pelican Bay", "Quillfeather", "Rosemead", "Stonebridge", "Thistledown",
    "Umberfield", "Vireo", "Willowmere", "Amberly", "Brightwater", "Copperleaf",
]

# --------------------------------------------------------------------------------------
# Product families (what a wholesaler pitches) and the fund line-up.
# demand: (start, end) logit shift over the simulation window, i.e. an industry trend.
# --------------------------------------------------------------------------------------
FAMILIES = {
    "CEQ": {"name": "Core Equity",                    "demand": (0.00, 0.05)},
    "GIE": {"name": "Growth & International Equity",  "demand": (-0.15, 0.20)},
    "EIO": {"name": "Equity Income & Options",        "demand": (0.35, 0.50)},
    "CFI": {"name": "Core Fixed Income",              "demand": (0.10, 0.30)},
    "SDC": {"name": "Short Duration & Cash Alternatives", "demand": (0.45, -0.30)},
    "CMU": {"name": "Credit & Municipal",             "demand": (0.00, 0.15)},
    "MAS": {"name": "Multi-Asset",                    "demand": (-0.15, -0.30)},
}

# betas = (equity, rates, credit); alpha = annual excess return vs category; carry = monthly
PRODUCTS = [
    # code       name                                   vehicle family asset_class    category                       fee  launch     betas            alpha  carry  idio
    ("AP-LCC",  "Aurora Peak US Large Cap Core Fund",     "MF",  "CEQ", "Equity",       "Large Blend",                 55, None,      (1.00, 0, 0),    0.005, 0.0,    0.010),
    ("AP-VAL",  "Aurora Peak US Value Fund",              "MF",  "CEQ", "Equity",       "Large Value",                 60, None,      (0.95, 0, 0),   -0.010, 0.0,    0.011),
    ("AP-QUAL", "Aurora Peak US Quality Factor ETF",      "ETF", "CEQ", "Equity",       "Large Blend",                 15, None,      (1.00, 0, 0),    0.002, 0.0,    0.006),
    ("AP-GRO",  "Aurora Peak US Growth Fund",             "MF",  "GIE", "Equity",       "Large Growth",                65, None,      (1.15, 0, 0),    0.015, 0.0,    0.013),
    ("AP-SMC",  "Aurora Peak Small Cap Fund",             "MF",  "GIE", "Equity",       "Small Blend",                 80, None,      (1.25, 0, 0),   -0.005, 0.0,    0.016),
    ("AP-INTL", "Aurora Peak International Equity Fund",  "MF",  "GIE", "Equity",       "Foreign Large Blend",         75, None,      (0.90, 0, 0),   -0.030, 0.0,    0.012),
    ("AP-EM",   "Aurora Peak Emerging Markets Fund",      "MF",  "GIE", "Equity",       "Diversified Emerging Mkts",   90, None,      (1.10, 0, 0),    0.000, 0.0,    0.018),
    ("AP-AGRO", "Aurora Peak Active Growth ETF",          "ETF", "GIE", "Equity",       "Large Growth",                45, "2025-07", (1.20, 0, 0),    0.020, 0.0,    0.012),
    ("AP-EPI",  "Aurora Peak Equity Premium Income ETF",  "ETF", "EIO", "Equity",       "Derivative Income",           35, None,      (0.60, 0, 0),    0.010, 0.0035, 0.007),
    ("AP-HEQ",  "Aurora Peak Hedged Equity Fund",         "MF",  "EIO", "Equity",       "Derivative Income",           58, None,      (0.55, 0, 0),    0.005, 0.0020, 0.006),
    ("AP-DIV",  "Aurora Peak Dividend Growth Fund",       "MF",  "EIO", "Equity",       "Large Value",                 50, None,      (0.85, 0, 0),    0.000, 0.0005, 0.009),
    ("AP-CB",   "Aurora Peak Core Bond Fund",             "MF",  "CFI", "Fixed Income", "Intermediate Core Bond",      35, None,      (0.00, 1.00, 0.10), 0.003, 0.0, 0.003),
    ("AP-CPB",  "Aurora Peak Core Plus Bond Fund",        "MF",  "CFI", "Fixed Income", "Intermediate Core-Plus Bond", 45, None,      (0.00, 0.90, 0.30), 0.006, 0.0, 0.004),
    ("AP-ACB",  "Aurora Peak Active Core Bond ETF",       "ETF", "CFI", "Fixed Income", "Intermediate Core Bond",      25, None,      (0.00, 1.00, 0.12), 0.004, 0.0, 0.003),
    ("AP-USI",  "Aurora Peak Ultra-Short Income ETF",     "ETF", "SDC", "Fixed Income", "Ultrashort Bond",             18, None,      (0.00, 0.15, 0.05), 0.002, 0.0030, 0.001),
    ("AP-SDI",  "Aurora Peak Short Duration Income Fund", "MF",  "SDC", "Fixed Income", "Short-Term Bond",             30, None,      (0.00, 0.30, 0.10), 0.000, 0.0025, 0.0015),
    ("AP-HY",   "Aurora Peak High Yield Fund",            "MF",  "CMU", "Fixed Income", "High Yield Bond",             55, None,      (0.20, 0.30, 0.80), -0.005, 0.0010, 0.006),
    ("AP-MUNI", "Aurora Peak Municipal Income Fund",      "MF",  "CMU", "Fixed Income", "Muni National Interm",        40, None,      (0.00, 0.80, 0.10), 0.004, 0.0, 0.003),
    ("AP-MAI",  "Aurora Peak Multi-Asset Income Fund",    "MF",  "MAS", "Multi-Asset",  "Moderate Allocation",         60, None,      (0.40, 0.40, 0.30), -0.008, 0.0010, 0.006),
    ("AP-GAL",  "Aurora Peak Global Allocation Fund",     "MF",  "MAS", "Multi-Asset",  "Global Allocation",           70, None,      (0.60, 0.30, 0.10), -0.012, 0.0, 0.008),
]
MF_SHARE_CLASSES = ["A", "C", "I"]

# Quarterly sales campaigns run by distribution marketing ("featured family").
CAMPAIGNS = {
    "2024Q1": "SDC", "2024Q2": "CFI", "2024Q3": "EIO", "2024Q4": "CEQ",
    "2025Q1": "EIO", "2025Q2": "CFI", "2025Q3": "GIE", "2025Q4": "GIE",
    "2026Q1": "CMU", "2026Q2": "EIO", "2026Q3": "CFI", "2026Q4": "MAS",
}

PRACTICE_FOCUS = {
    # focus: (share, affinity shift per family)
    "Retirement Income":   (0.26, {"EIO": 0.9, "CFI": 0.6, "MAS": 0.5, "SDC": 0.3, "CMU": 0.2, "CEQ": 0.0, "GIE": -0.5}),
    "Growth Accumulation": (0.24, {"GIE": 1.0, "CEQ": 0.6, "EIO": -0.2, "CFI": -0.3, "SDC": -0.4, "CMU": -0.3, "MAS": -0.2}),
    "High Net Worth":      (0.20, {"CMU": 0.8, "CEQ": 0.5, "EIO": 0.4, "GIE": 0.2, "CFI": 0.1, "SDC": 0.2, "MAS": -0.4}),
    "Mass Affluent":       (0.18, {"MAS": 0.9, "CEQ": 0.4, "CFI": 0.3, "EIO": 0.1, "GIE": 0.0, "SDC": -0.1, "CMU": -0.4}),
    "Tax-Aware":           (0.12, {"CMU": 1.1, "CEQ": 0.4, "SDC": 0.3, "CFI": 0.2, "EIO": 0.0, "GIE": 0.0, "MAS": -0.3}),
}

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David",
    "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas",
    "Sarah", "Charles", "Karen", "Daniel", "Lisa", "Matthew", "Nancy", "Anthony", "Betty",
    "Mark", "Sandra", "Steven", "Ashley", "Andrew", "Emily", "Joshua", "Michelle", "Kevin",
    "Amanda", "Brian", "Melissa", "George", "Stephanie", "Timothy", "Rebecca", "Ryan",
    "Laura", "Jason", "Rachel", "Eric", "Megan", "Jacob", "Hannah", "Priya", "Arjun", "Wei",
    "Mei", "Carlos", "Sofia", "Luis", "Elena", "Omar", "Aisha", "Hiroshi", "Yuki", "Raj",
    "Ananya", "Kwame", "Amara", "Diego", "Lucia", "Noah", "Olivia", "Ethan", "Ava",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter",
    "Roberts", "Patel", "Shah", "Chen", "Wang", "Kim", "Park", "Singh", "Kumar", "Okafor",
    "Mensah", "Tanaka", "Sato", "Iyer", "Reddy", "Costa", "Silva", "Novak", "Kowalski",
]

INSTITUTION_TYPES = {
    "Public Pension": "Employees' Retirement Fund",
    "Corporate DB": "Corporate Pension Plan",
    "Endowment/Foundation": "Foundation",
    "Insurance": "Insurance Group",
}
INSTITUTIONAL_STRATEGIES = ["AP-CB", "AP-CPB", "AP-LCC", "AP-INTL", "AP-HY", "AP-GAL"]
