# services/ai_service.py
"""
AI Service - All Gemini AI operations

This file is the BRAIN of your AI features.
Every AI operation in the entire app goes through here.
Routers call these functions, they call Gemini.
"""


import os                              # For reading environment variables
import google.generativeai as genai    # Google's AI library
from dotenv import load_dotenv         # For loading .env file
from typing import List, Dict, Optional  # Type hints

# Load .env file so we can read GEMINI_API_KEY
load_dotenv()


# ─────────────────────────────────────────────────────
# SETUP GEMINI
# This happens ONCE when the file is first imported
# Think of it like creating an axios instance in Next.js
# ─────────────────────────────────────────────────────

# Configure with our API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
#               ↑
#               os.getenv reads from .env file
#               NEVER write the key directly here


# Create the AI model
model = genai.GenerativeModel(
    
    # model_name="models/gemini-1.5-flash",
    model_name="models/gemini-2.5-flash",
    #           ↑
    #           Which Gemini model to use
    #           "gemini-1.5-flash" = fast + free
    #           "gemini-1.5-pro"   = smarter but limited free tier
    #           We use flash because it's fast and free
    
    system_instruction="""
    You are a friendly personal finance advisor called FinanceAI.
    
    Your personality:
    - Encouraging and positive
    - Practical and specific  
    - Simple language (no jargon)
    - Data-driven (use the actual numbers given)
    
    Your format:
    - Use bullet points for lists
    - Use emojis sparingly for readability
    - Keep responses concise
    - Always end with an actionable tip
    """
    # ↑
    # system_instruction = personality of the AI
    # This applies to EVERY response from this model
    # Like telling a new employee how to behave
)


# ─────────────────────────────────────────────────────
# HELPER FUNCTION: Format Transactions
# ─────────────────────────────────────────────────────

def format_transactions_for_ai(transactions: List[Dict]) -> str:
    """
    Convert Python list of dicts → readable text for AI
    
    WHY WE NEED THIS:
    AI understands text, not Python objects
    
    INPUT:
    [
        {"type": "expense", "category": "Food", "amount": 500},
        {"type": "income",  "category": "Salary", "amount": 5000}
    ]
    
    OUTPUT:
    "- EXPENSE: Food - $500.00 (no description)
     - INCOME: Salary - $5000.00 (monthly salary)"
    
    The AI reads this text and understands your finances
    """
    
    # Handle empty case
    if not transactions:
        return "No transactions found."
    
    formatted_lines = []
    
    for transaction in transactions:
        # Build one line per transaction
        line = (
            f"- {transaction['type'].upper()}: "
            #    ↑                   ↑
            #    dash for readability  .upper() = INCOME not income
            
            f"{transaction['category']} "
            #  ↑ Category name
            
            f"- ${float(transaction['amount']):.2f} "
            #      ↑              ↑
            #      dollar sign    :.2f = 2 decimal places (500.00)
            
            f"({transaction.get('description', 'no description')})"
            #   ↑
            #   .get with default = if no description, show "no description"
        )
        formatted_lines.append(line)
    
    # Join all lines with newline
    return "\n".join(formatted_lines)
    # "\n".join = put each line on its own line


# ─────────────────────────────────────────────────────
# FEATURE 1: Financial Insights
# Analyze ALL transactions at once
# ─────────────────────────────────────────────────────

def get_financial_insights(
    transactions: List[Dict],  # All user transactions
    summary: Dict              # Income/expense/balance totals
) -> str:                      # Returns text from AI
    """
    Get comprehensive AI analysis of finances
    
    WHAT IT DOES:
    1. Takes all transactions and summary
    2. Formats them as readable text
    3. Asks Gemini to analyze them
    4. Returns Gemini's analysis
    
    CALLED FROM:
    GET /ai/insights endpoint
    """
    
    # Step 1: Format transactions as text
    transactions_text = format_transactions_for_ai(transactions)
    
    # Step 2: Build the prompt
    # This is what we send to Gemini
    # The more specific and structured, the better the response
    prompt = f"""
Please analyze my financial data below:

═══ FINANCIAL SUMMARY ═══
- Total Income:    ${summary['total_income']:.2f}
- Total Expenses:  ${summary['total_expense']:.2f}
- Current Balance: ${summary['balance']:.2f}
- Total Transactions: {summary['transaction_count']}

═══ ALL TRANSACTIONS ═══
{transactions_text}

Please provide:
1. 📊 SPENDING PATTERNS - What patterns do you notice?
2. 🔴 TOP SPENDING AREAS - Where am I spending most?
3. 💚 FINANCIAL HEALTH - Is my spending healthy overall?
4. 💡 TOP 3 RECOMMENDATIONS - Specific things I can do
5. ⭐ ONE POSITIVE - Something good about my finances

Be specific using my actual numbers.
Keep total response under 300 words.
"""
    # f""" = f-string with triple quotes
    # Allows multi-line strings with variables
    # {summary['total_income']:.2f} = formats number to 2 decimals
    
    # Step 3: Send to Gemini and get response
    response = model.generate_content(prompt)
    #                ↑
    #                generate_content = send prompt, get response
    #                This is the actual API call to Google
    #                Takes 1-3 seconds
    
    # Step 4: Return just the text
    return response.text
    #               ↑
    #               .text = the actual string response
    #               response also has other data we don't need


# ─────────────────────────────────────────────────────
# FEATURE 2: AI Chat
# Ask questions about YOUR finances
# ─────────────────────────────────────────────────────

def chat_with_ai(
    user_message: str,                      # What user asked
    transactions: List[Dict],               # Their data (context)
    summary: Dict,                          # Their summary (context)
    chat_history: Optional[List[Dict]] = None  # Previous messages
) -> str:
    """
    Have a conversation with AI about finances
    
    KEY CONCEPT - CONTEXT:
    AI has no memory between sessions
    So we send ALL their financial data
    with EVERY message
    
    This gives AI "memory" of their finances
    even though it's technically stateless
    
    CHAT HISTORY:
    We also send previous messages
    So AI knows what was already discussed
    
    EXAMPLE:
    User: "Where am I overspending?"
    AI: "You're overspending on Food ($500)"
    User: "How can I fix that?"
    AI: (knows we're talking about Food from history)
        "To reduce food spending, try meal prepping..."
    """
    
    # Step 1: Format financial data as context
    transactions_text = format_transactions_for_ai(transactions)
    
    context = f"""
The user asking you questions has this financial data:

SUMMARY:
- Income: ${summary['total_income']:.2f}
- Expenses: ${summary['total_expense']:.2f}
- Balance: ${summary['balance']:.2f}

TRANSACTIONS:
{transactions_text}

Answer their question using this specific data.
Reference their actual numbers when relevant.
"""
    
    # Step 2: Start a chat session
    chat_session = model.start_chat(history=[])
    #                    ↑
    #                    start_chat() = creates conversation
    #                    history=[] = start fresh
    #                    We manually add history below
    
    # Step 3: Send financial context first
    # This gives AI knowledge of user's finances
    chat_session.send_message(context)
    #            ↑
    #            send_message() = send one message
    #            We ignore this response (it's just setup)
    
    # Step 4: Add previous chat messages (if any)
    # This gives AI memory of conversation
    if chat_history:
        for previous_message in chat_history:
            # Only add user messages to history
            # (to avoid sending AI responses back as input)
            if previous_message.get('role') == 'user':
                chat_session.send_message(previous_message['content'])
    
    # Step 5: Send the actual user question
    response = chat_session.send_message(user_message)
    
    # Step 6: Return AI's answer
    return response.text


# ─────────────────────────────────────────────────────
# FEATURE 3: Category-Specific Advice
# Get advice for ONE spending category
# ─────────────────────────────────────────────────────

def get_spending_advice(
    category: str,        # e.g. "Food"
    amount: float,        # e.g. 500.00
    total_income: float   # e.g. 5000.00
) -> str:
    """
    Get AI advice for a specific spending category
    
    EXAMPLE:
    category = "Food"
    amount = 500
    income = 5000
    
    AI tells you:
    - Is $500 on food healthy?
    - What % of income should food be?
    - Specific tips to reduce food spending
    """
    
    # Calculate percentage
    if total_income > 0:
        percentage = (amount / total_income) * 100
    else:
        percentage = 0
    # Guard against division by zero
    # If income is 0, percentage is 0
    
    prompt = f"""
My spending on {category}:
- Amount spent: ${amount:.2f}
- My total income: ${total_income:.2f}
- This is {percentage:.1f}% of my income

Please tell me:
1. Is ${amount:.2f} on {category} healthy?
2. What percentage of income should {category} be?
3. Give me 3 specific tips to optimize {category} spending

Keep response under 150 words.
Be specific and practical.
"""
    
    response = model.generate_content(prompt)
    return response.text