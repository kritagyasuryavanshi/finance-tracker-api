# services/finance_crew.py
"""
CrewAI Multi-Agent Financial Analysis System

THREE SPECIALIZED AGENTS:
1. Data Analyst     - Reads and analyzes raw transaction data
2. Financial Advisor - Interprets data, creates recommendations  
3. Report Writer    - Writes beautiful, clear final report

They work SEQUENTIALLY:
Analyst output → Advisor input → Writer input → Final Report
"""

# ─────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────

import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
# ↑ Load .env so GEMINI_API_KEY is available


# CrewAI imports
from crewai import LLM, Agent, Task, Crew, Process
# Agent  = one AI team member with role/goal/tools
# Task   = specific job assigned to an agent
# Crew   = the whole team + how they work together
# Process = how agents collaborate (sequential/hierarchical)

from crewai.tools import tool
# ↑ Decorator to create tools agents can use
#   Like @tool in LangChain but for CrewAI
#   Agent sees tool description and decides when to use it

from langchain_google_genai import ChatGoogleGenerativeAI
# ↑ Gemini AI - the "brain" for all our agents
#   Each agent shares the same LLM
#   But has different role/goal/backstory
#   So they "think" differently despite same brain!

load_dotenv()

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# ─────────────────────────────────────────────────────
# SETUP LLM
# ─────────────────────────────────────────────────────

llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7,
)
# ↑ Created ONCE, shared by ALL agents
#   Like one company buying one ChatGPT subscription
#   All employees use the same subscription


# ─────────────────────────────────────────────────────
# GLOBAL STATE
# Stores user data during crew execution
# ─────────────────────────────────────────────────────

_current_transactions: List[Dict] = []
_current_summary: Dict = {}
# ↑ Global variables to store data during analysis
#
# WHY GLOBAL?
# CrewAI tools are standalone functions
# They can't receive parameters from the crew
# So we store data globally before running crew
# Tools then read from these globals
#
# FLOW:
# 1. API endpoint sets these globals
# 2. Crew starts
# 3. Tools read from globals
# 4. Crew finishes
# 5. API returns result
#
# Not perfect but simple and works well!


# ─────────────────────────────────────────────────────
# TOOLS
# Functions that agents can call during their work
# ─────────────────────────────────────────────────────

@tool("Get All Transactions")
def get_all_transactions_tool(query: str = "all") -> str:
    """
    Get all financial transactions for the current user.
    Use this to retrieve raw transaction data for analysis.
    Returns formatted transaction list with dates, categories, and amounts.
    """
    # ↑ DOCSTRING IS CRITICAL!
    #   Agent reads this to decide WHEN to use tool
    #   More descriptive = agent uses it more accurately
    #
    # "Get all financial transactions" tells agent:
    # "Use me when you need transaction data"
    # "Returns formatted transaction list" tells agent:
    # "I give you text, not a Python object"
    
    global _current_transactions
    # ↑ Access global variable
    #   This was set before crew started
    
    if not _current_transactions:
        return "No transactions found. The user has no transaction data."
    
    # Format transactions as readable text
    lines = ["TRANSACTION DATA:", "=" * 40]
    
    for i, t in enumerate(_current_transactions, 1):
        # enumerate starts counting from 1
        line = (
            f"{i}. {t.get('date', 'N/A')} | "
            f"{t.get('type', 'N/A').upper()} | "
            f"{t.get('category', 'N/A')} | "
            f"${float(t.get('amount', 0)):.2f} | "
            f"{t.get('description', 'No description')}"
        )
        lines.append(line)
    
    lines.append("=" * 40)
    lines.append(f"TOTAL TRANSACTIONS: {len(_current_transactions)}")
    
    return "\n".join(lines)
    # ↑ Return as text (agents understand text best)


@tool("Get Financial Summary")
def get_financial_summary_tool(query: str = "summary") -> str:
    """
    Get the financial summary showing total income, expenses, and balance.
    Use this to understand the overall financial picture.
    Returns total income, total expenses, balance, and transaction count.
    """
    
    global _current_summary
    
    if not _current_summary:
        return "No financial summary available."
    
    total_income = _current_summary.get("total_income", 0)
    total_expense = _current_summary.get("total_expense", 0)
    balance = _current_summary.get("balance", 0)
    count = _current_summary.get("transaction_count", 0)
    
    # Calculate savings rate
    if total_income > 0:
        savings_rate = ((total_income - total_expense) / total_income) * 100
        expense_ratio = (total_expense / total_income) * 100
    else:
        savings_rate = 0
        expense_ratio = 0
    
    summary_text = f"""
FINANCIAL SUMMARY
{"=" * 40}
Total Income:      ${total_income:.2f}
Total Expenses:    ${total_expense:.2f}
Current Balance:   ${balance:.2f}
Transactions:      {count}
{"=" * 40}
Savings Rate:      {savings_rate:.1f}%
Expense Ratio:     {expense_ratio:.1f}%
{"=" * 40}
HEALTH INDICATOR:
{"✅ HEALTHY" if savings_rate >= 20 else "⚠️ NEEDS ATTENTION" if savings_rate >= 10 else "🚨 CRITICAL"}
Reason: {"Saving 20%+ of income" if savings_rate >= 20 else "Saving 10-20%" if savings_rate >= 10 else "Saving less than 10%"}
""".strip()
    
    return summary_text


@tool("Calculate Category Totals")
def calculate_category_totals_tool(query: str = "all categories") -> str:
    """
    Calculate total spending by category.
    Use this to find which categories have highest spending.
    Returns spending breakdown by category with percentages.
    """
    
    global _current_transactions, _current_summary
    
    if not _current_transactions:
        return "No transaction data available for category analysis."
    
    # Group transactions by category
    categories: Dict[str, float] = {}
    # ↑ Dict[str, float] = type hint
    #   keys = category names (strings)
    #   values = total amounts (floats)
    
    for t in _current_transactions:
        category = t.get("category", "Unknown")
        amount = float(t.get("amount", 0))
        tx_type = t.get("type", "")
        
        # Only count expenses for spending analysis
        if tx_type == "expense":
            if category in categories:
                categories[category] += amount
                # ↑ Add to existing category
            else:
                categories[category] = amount
                # ↑ Create new category
    
    if not categories:
        return "No expense transactions found."
    
    # Sort by amount (highest first)
    sorted_categories = sorted(
        categories.items(),
        key=lambda x: x[1],
        # ↑ Sort by value (amount)
        # lambda x: x[1] = "use second element for sorting"
        # x[0] = category name, x[1] = amount
        reverse=True
        # ↑ Highest first
    )
    
    total_expenses = _current_summary.get("total_expense", 1)
    # ↑ Use 1 as default to avoid division by zero
    
    lines = ["SPENDING BY CATEGORY:", "=" * 40]
    
    for rank, (category, amount) in enumerate(sorted_categories, 1):
        # enumerate gives us index AND value
        percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
        bar = "█" * int(percentage / 5)
        # ↑ Visual bar chart using block character
        #   20% = ████, 40% = ████████
        
        lines.append(
            f"{rank}. {category:<20} ${amount:>8.2f} ({percentage:.1f}%) {bar}"
            # {category:<20} = left-align, pad to 20 chars
            # ${amount:>8.2f} = right-align, 2 decimals
        )
    
    lines.append("=" * 40)
    return "\n".join(lines)


@tool("Identify Spending Patterns")
def identify_patterns_tool(query: str = "patterns") -> str:
    """
    Identify unusual spending patterns and trends.
    Use this to find anomalies, recurring expenses, and trends.
    Returns list of patterns and anomalies found in transaction data.
    """
    
    global _current_transactions, _current_summary
    
    if not _current_transactions:
        return "No data available for pattern analysis."
    
    patterns = []
    
    # Pattern 1: Find largest transactions
    sorted_by_amount = sorted(
        _current_transactions,
        key=lambda x: float(x.get("amount", 0)),
        reverse=True
    )
    
    if sorted_by_amount:
        largest = sorted_by_amount[0]
        patterns.append(
            f"💰 LARGEST TRANSACTION: "
            f"{largest.get('category')} - "
            f"${float(largest.get('amount', 0)):.2f}"
        )
    
    # Pattern 2: Count transactions by type
    income_count = sum(1 for t in _current_transactions if t.get("type") == "income")
    expense_count = sum(1 for t in _current_transactions if t.get("type") == "expense")
    # ↑ sum() with generator expression
    #   Counts transactions matching condition
    #   Elegant Python pattern!
    
    patterns.append(f"📊 TRANSACTION SPLIT: {income_count} income, {expense_count} expense")
    
    # Pattern 3: Check expense ratio
    total_income = _current_summary.get("total_income", 0)
    total_expense = _current_summary.get("total_expense", 0)
    
    if total_income > 0:
        ratio = total_expense / total_income
        if ratio > 1:
            patterns.append("🚨 CRITICAL: Spending MORE than earning!")
        elif ratio > 0.9:
            patterns.append("⚠️ WARNING: Spending 90%+ of income - very little savings")
        elif ratio > 0.7:
            patterns.append("⚡ CAUTION: Spending 70-90% of income")
        else:
            patterns.append("✅ GOOD: Spending less than 70% of income")
    
    # Pattern 4: Find most frequent category
    category_counts: Dict[str, int] = {}
    for t in _current_transactions:
        cat = t.get("category", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    if category_counts:
        most_frequent = max(category_counts, key=category_counts.get)
        # ↑ Find key with highest value
        #   max() with key function
        patterns.append(
            f"🔄 MOST FREQUENT: {most_frequent} "
            f"({category_counts[most_frequent]} transactions)"
        )
    
    # Pattern 5: Balance health
    balance = _current_summary.get("balance", 0)
    if balance < 0:
        patterns.append(f"🚨 NEGATIVE BALANCE: ${balance:.2f} - Overspending!")
    elif balance > 0:
        patterns.append(f"✅ POSITIVE BALANCE: ${balance:.2f} saved")
    
    result = "SPENDING PATTERNS & ANOMALIES:\n" + "=" * 40 + "\n"
    result += "\n".join(patterns)
    return result


# ─────────────────────────────────────────────────────
# AGENTS
# The specialized team members
# ─────────────────────────────────────────────────────

def create_data_analyst() -> Agent:
    """
    Create the Data Analyst agent
    
    RESPONSIBILITY:
    Read raw transaction data
    Calculate totals and percentages
    Find patterns and anomalies
    Produce structured data summary
    
    WHY SEPARATE FROM ADVISOR?
    Analysis and advice are different skills
    Analyst is objective (just numbers)
    Advisor is subjective (interpretation)
    Separation = better quality output
    """
    
    return Agent(
        role="Senior Personal Finance Data Analyst",
        # ↑ The agent's job title
        #   Shapes how it approaches tasks
        #   More specific = better results
        
        goal="""Thoroughly analyze the user's financial transactions 
        to provide accurate, data-driven insights about their 
        spending patterns, income sources, and financial trends.
        Always back findings with specific numbers.""",
        # ↑ What this agent is trying to ACHIEVE
        #   Guides agent's decision making
        #   "Always back findings with specific numbers"
        #   = agent will include real numbers in output
        
        backstory="""You are a Senior Data Analyst with 12 years of 
        experience at top financial institutions including JPMorgan 
        and Goldman Sachs. You specialize in personal finance analysis 
        and have analyzed over 10,000 client portfolios.
        
        Your analytical approach:
        - You never make claims without data to back them up
        - You always quantify findings (percentages, totals, ratios)
        - You identify patterns others miss
        - You present data clearly and objectively
        - You're detail-oriented and thorough
        
        You believe: "Numbers don't lie, but they do tell stories.
        Your job is to find and tell that story accurately."
        """,
        # ↑ The MOST IMPORTANT field!
        #   More detailed backstory = better agent
        #   Agent "becomes" this persona
        #   JPMorgan/Goldman Sachs reference = higher quality output
        #   Specific traits guide behavior
        
        tools=[
            get_all_transactions_tool,
            get_financial_summary_tool,
            calculate_category_totals_tool,
            identify_patterns_tool
        ],
        # ↑ What tools this agent can use
        #   Agent decides WHEN to use each tool
        #   Based on tool name + description
        
        llm=llm,
        # ↑ Which LLM to use as brain
        #   Same Gemini for all agents
        
        verbose=True,
        # ↑ Print agent's thinking to terminal
        #   Great for debugging!
        #   Shows: Thought → Action → Observation
        
        allow_delegation=False,
        # ↑ Can this agent give tasks to other agents?
        #   False = stays focused on its own task
        #   True = can delegate (for hierarchical process)
        
        max_iter=5,
        # ↑ Maximum thinking iterations
        #   Prevents infinite loops
        #   5 = think 5 times max before answering
    )


def create_financial_advisor() -> Agent:
    """
    Create the Financial Advisor agent
    
    RESPONSIBILITY:
    Interpret analyst's data
    Compare to healthy benchmarks
    Create personalized recommendations
    Prioritize advice by impact
    """
    
    return Agent(
        role="Certified Personal Financial Advisor",
        
        goal="""Transform raw financial data into actionable, 
        personalized advice that helps users improve their 
        financial health. Create specific, implementable 
        recommendations with expected outcomes.""",
        
        backstory="""You are a Certified Financial Planner (CFP) with 
        15 years of experience helping individuals achieve financial 
        freedom. You've worked with clients ranging from fresh graduates 
        to millionaires.
        
        Your expertise includes:
        - Budget optimization (50/30/20 rule specialist)
        - Debt reduction strategies
        - Emergency fund planning
        - Investment basics for beginners
        - Behavioral finance (why people make bad money decisions)
        
        Your philosophy:
        - Everyone can improve their finances regardless of income
        - Small consistent changes create massive long-term impact
        - Advice must be SPECIFIC and ACTIONABLE, not generic
        - You meet clients where they are, not where you think they should be
        
        Your communication style:
        - Warm and encouraging but honest
        - Use real numbers from their data
        - Prioritize advice by impact (highest ROI first)
        - Give specific dollar amounts and timelines
        
        You believe: "A plan without action is just a wish. 
        My job is to turn wishes into concrete plans."
        """,
        
        tools=[
            get_financial_summary_tool,
            calculate_category_totals_tool,
        ],
        # ↑ Advisor needs less raw data
        #   Gets analysis from analyst's output
        #   Only needs summary + categories to advise
        
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )


def create_report_writer() -> Agent:
    """
    Create the Report Writer agent
    
    RESPONSIBILITY:
    Take analyst + advisor outputs
    Combine into beautiful report
    Make it readable and actionable
    Format for end user consumption
    """
    
    return Agent(
        role="Financial Report Specialist",
        
        goal="""Create clear, engaging, and actionable financial 
        reports that turn complex analysis and advice into 
        easy-to-understand documents that motivate positive change.""",
        
        backstory="""You are a specialist in financial communication 
        with a background in both finance and journalism. You've 
        written reports for Fortune 500 companies and personal 
        finance publications.
        
        Your writing principles:
        - Clarity above all else (a confused reader does nothing)
        - Structure matters (good report = good decisions)
        - Numbers need context (not just $500, but "$500 which is 20% of income")
        - End with hope and clear next steps
        - Use formatting to guide the eye (headers, bullets, emphasis)
        
        Your reports always include:
        1. Executive summary (key findings in 3 lines)
        2. Detailed analysis section
        3. Specific recommendations
        4. 30-day action plan
        5. Motivational closing
        
        You believe: "The best financial report is one that 
        someone actually reads AND acts on. Beautiful writing 
        that collects dust helps no one."
        """,
        
        tools=[],
        # ↑ Writer needs NO tools!
        #   Gets all information from previous agents
        #   Just needs to write and format
        #   Pure language task = no tool access needed
        
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
        # ↑ Writer needs fewer iterations
        #   Just writing, not researching
    )


# ─────────────────────────────────────────────────────
# TASKS
# Specific jobs for each agent
# ─────────────────────────────────────────────────────

def create_analysis_task(analyst: Agent) -> Task:
    """
    Task for Data Analyst agent
    
    WHAT IT DOES:
    Uses all tools to gather and analyze financial data
    Produces structured analysis for advisor to use
    """
    
    return Task(
        description="""
        Conduct a thorough analysis of the user's financial data.
        
        You MUST use your available tools to:
        1. Get all transactions (use Get All Transactions tool)
        2. Get the financial summary (use Get Financial Summary tool)
        3. Calculate spending by category (use Calculate Category Totals tool)
        4. Identify patterns (use Identify Spending Patterns tool)
        
        After gathering data with tools, analyze:
        - What are the top 3 spending categories?
        - What is the income vs expense ratio?
        - What is the savings rate?
        - Are there any red flags or unusual patterns?
        - What percentage of income goes to each major category?
        
        Be specific. Use real numbers from the data.
        """,
        # ↑ VERY specific instructions
        #   Lists EXACTLY what to do step by step
        #   Tells agent to use specific tools
        #   "You MUST" = forces agent to actually use tools
        
        expected_output="""
        A comprehensive data analysis report containing:
        
        1. FINANCIAL OVERVIEW
           - Total income, expenses, balance with exact amounts
           - Savings rate percentage
           - Health status (healthy/needs attention/critical)
        
        2. SPENDING BREAKDOWN
           - Top 5 spending categories with amounts AND percentages of income
           - Visual representation if possible
        
        3. PATTERNS FOUND
           - List of patterns and anomalies identified
           - Any unusual or recurring transactions
        
        4. KEY METRICS
           - Income to expense ratio
           - Average transaction amount
           - Most frequent spending category
        
        Format: Structured sections with headers
        Include: Real numbers from actual data (no approximations)
        Tone: Objective and analytical
        """,
        # ↑ Tells agent EXACTLY what format to return
        #   Without this: agent returns whatever it wants
        #   With this: consistent, structured output
        #   Next agent relies on this structure!
        
        agent=analyst,
        # ↑ Which agent does this task
        #   Must be the analyst agent we created
    )


def create_advice_task(advisor: Agent) -> Task:
    """
    Task for Financial Advisor agent
    
    WHAT IT DOES:
    Takes analyst's output (automatically provided by CrewAI)
    Creates personalized recommendations
    Prioritizes by impact
    """
    
    return Task(
        description="""
        Based on the data analysis provided by the Data Analyst,
        create personalized financial advice for this user.
        
        You can also use your tools to verify specific numbers.
        
        Your advice should:
        1. Address the most critical financial issues first
        2. Apply the 50/30/20 budgeting rule as benchmark
           (50% needs, 30% wants, 20% savings)
        3. Identify specific areas where they're overspending
        4. Calculate exactly how much they should cut from each category
        5. Set a realistic 30-day savings goal
        6. Suggest 3 immediate actions they can take TODAY
        
        Consider:
        - Their current savings rate vs recommended 20%
        - Which spending categories are highest vs benchmarks
        - Their balance trend (positive/negative)
        
        Be specific. Say "$50 less on Food" not "reduce food spending."
        """,
        
        expected_output="""
        A personalized financial advice report containing:
        
        1. FINANCIAL HEALTH ASSESSMENT
           - Current status with specific reasoning
           - How they compare to healthy benchmarks
        
        2. TOP 3 PRIORITY ACTIONS
           - Most impactful changes ranked by importance
           - Specific dollar amounts for each recommendation
           - Expected outcome if implemented
        
        3. BUDGET OPTIMIZATION
           - Current vs recommended spending per category
           - Specific reductions needed with amounts
        
        4. 30-DAY SAVINGS GOAL
           - Specific achievable target based on their data
           - Step-by-step plan to achieve it
        
        5. IMMEDIATE ACTIONS (can do today)
           - 3 concrete steps to take right now
        
        Format: Action-oriented with specific numbers
        Tone: Encouraging but honest
        """,
        
        agent=advisor,
        # ↑ Assigned to advisor agent
        
        context=[],
        # ↑ We'll set this when building crew
        #   CrewAI handles passing analyst output automatically
        #   In sequential process, previous task output
        #   is automatically provided as context!
    )


def create_report_task(writer: Agent) -> Task:
    """
    Task for Report Writer agent
    
    WHAT IT DOES:
    Takes BOTH analyst + advisor outputs
    Writes final polished report
    """
    
    return Task(
        description="""
        Create a comprehensive, well-formatted financial report
        that combines the data analysis and financial advice
        provided by the previous team members.
        
        The report should feel professional yet personal.
        Someone reading this should feel both informed AND motivated.
        
        Structure the report with:
        - Clear headers and sections
        - Real numbers throughout (from the analysis)
        - Specific actionable steps
        - Encouraging tone that motivates change
        - A clear 30-day action plan at the end
        
        Make it the kind of report someone would pay $200 for
        from a real financial advisor.
        """,
        
        expected_output="""
        A complete financial analysis report with this EXACT structure:
        
        💰 PERSONAL FINANCIAL ANALYSIS REPORT
        ==========================================
        
        📊 EXECUTIVE SUMMARY
        [3-line summary of key findings]
        
        💵 YOUR FINANCIAL PICTURE
        [Detailed summary with all numbers]
        
        📈 SPENDING ANALYSIS
        [Category breakdown with visuals]
        
        🔍 KEY PATTERNS FOUND
        [Important patterns identified]
        
        💡 PERSONALIZED RECOMMENDATIONS
        [Specific advice with dollar amounts]
        
        🎯 YOUR 30-DAY ACTION PLAN
        [Week by week plan with specific actions]
        
        ⭐ CLOSING MOTIVATION
        [Encouraging close that motivates action]
        
        Use emojis for visual appeal.
        Include ALL specific numbers from the analysis.
        Keep total length under 600 words.
        """,
        
        agent=writer,
    )


# ─────────────────────────────────────────────────────
# BUILD AND RUN CREW
# ─────────────────────────────────────────────────────

def run_finance_crew(
    transactions: List[Dict],
    summary: Dict,
    user_id: str
) -> str:
    """
    Run the complete multi-agent financial analysis crew
    
    ARGS:
    transactions: List of user's transactions from DB
    summary: Financial summary dict
    user_id: User's ID (for logging)
    
    RETURNS:
    Final report as string
    
    HOW IT WORKS:
    1. Set global data (tools read from this)
    2. Create agents
    3. Create tasks
    4. Build crew
    5. Run crew (kickoff!)
    6. Return final output
    """
    
    # Step 1: Set global data for tools to access
    global _current_transactions, _current_summary
    _current_transactions = transactions
    _current_summary = summary
    # ↑ Tools will read from these globals
    #   Set before running crew so tools have data
    
    # Validate data
    if not transactions:
        return """
💰 FINANCIAL ANALYSIS REPORT
==============================
⚠️ NO DATA AVAILABLE

You haven't added any transactions yet!

To get your personalized financial analysis:
1. Go to the Dashboard tab
2. Add some income transactions (your salary, etc.)
3. Add some expense transactions (food, rent, etc.)
4. Come back and run the analysis!

The more transactions you add, the more accurate
and personalized your analysis will be.
""".strip()
    
    # Step 2: Create agents
    analyst = create_data_analyst()
    advisor = create_financial_advisor()
    writer = create_report_writer()
    # ↑ Create fresh agents for each run
    #   Ensures clean state
    
    # Step 3: Create tasks
    analysis_task = create_analysis_task(analyst)
    advice_task = create_advice_task(advisor)
    report_task = create_report_task(writer)
    # ↑ Tasks are linked to specific agents
    
    # Step 4: Build the crew
    crew = Crew(
        agents=[analyst, advisor, writer],
        # ↑ The team members
        #   Order matters for sequential process!
        
        tasks=[analysis_task, advice_task, report_task],
        # ↑ The jobs to complete
        #   Order = execution order
        #   Task 1 → Task 2 → Task 3
        
        process=Process.sequential,
        # ↑ HOW agents work together:
        #
        # Process.sequential:
        #   Task 1 completes → output given to Task 2
        #   Task 2 completes → output given to Task 3
        #   Task 3 completes → final output
        #   Like an assembly line
        #
        # Process.hierarchical:
        #   Manager agent coordinates other agents
        #   More autonomous but less predictable
        #   We use sequential for reliability
        
        verbose=True,
        # ↑ Print crew's progress to terminal
        #   Shows which agent is working
        #   Shows tools being called
        #   VERY helpful for debugging!
        
        memory=False,
        # ↑ Don't remember between different crew runs
        #   Each analysis starts fresh
        #   True would remember across runs (we don't need this)
    )
    
    # Step 5: RUN THE CREW!
    try:
        result = crew.kickoff()
        # ↑ This starts the whole process:
        #   1. Analyst agent starts
        #   2. Analyst uses tools to gather data
        #   3. Analyst writes analysis
        #   4. Advisor receives analyst's output
        #   5. Advisor creates recommendations
        #   6. Writer receives both outputs
        #   7. Writer creates final report
        #   8. Returns final report
        #
        # Takes 30-60 seconds (multiple AI calls!)
        # This is normal for multi-agent systems
        
        # Extract the text from CrewAI result
        if hasattr(result, 'raw'):
            return result.raw
            # ↑ result.raw = plain text output
            #   CrewAI returns a CrewOutput object
            #   .raw = the actual text string
        else:
            return str(result)
            # ↑ Fallback: convert to string
    
    except Exception as e:
        return f"""
💰 FINANCIAL ANALYSIS REPORT
==============================
❌ Analysis encountered an error: {str(e)}

Please try again. If the error persists,
make sure you have transactions added to your account.
""".strip()
    
    finally:
        # Clean up globals after run
        _current_transactions = []
        _current_summary = {}
        # ↑ Clear globals so they don't persist
        #   Next run starts with clean state