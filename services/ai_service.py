# services/ai_service.py
"""
AI Service - All Gemini AI operations
Uses google.genai (new package, replaces google.generativeai)
"""

import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from typing import List, Dict, Optional

load_dotenv()

# ─────────────────────────────────────────────────────
# SETUP GEMINI CLIENT (new way)
# ─────────────────────────────────────────────────────

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)
# ↑ New package uses Client instead of configure()
#   Same API key, different setup pattern

MODEL = "gemini-2.5-flash"
# ↑ Store model name as constant
#   Easy to change in one place if needed

SYSTEM_INSTRUCTION = """
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


# ─────────────────────────────────────────────────────
# HELPER: Format Transactions
# ─────────────────────────────────────────────────────

def format_transactions_for_ai(transactions: List[Dict]) -> str:
    """Convert transaction list to readable text for AI"""
    if not transactions:
        return "No transactions found."

    formatted_lines = []
    for transaction in transactions:
        line = (
            f"- {transaction['type'].upper()}: "
            f"{transaction['category']} "
            f"- ${float(transaction['amount']):.2f} "
            f"({transaction.get('description', 'no description')})"
        )
        formatted_lines.append(line)

    return "\n".join(formatted_lines)


# ─────────────────────────────────────────────────────
# FEATURE 1: Financial Insights
# ─────────────────────────────────────────────────────

def get_financial_insights(
    transactions: List[Dict],
    summary: Dict
) -> str:
    """Get comprehensive AI analysis of finances"""

    transactions_text = format_transactions_for_ai(transactions)

    prompt = f"""
Please analyze my financial data below:

═══ FINANCIAL SUMMARY ═══
- Total Income:       ${summary['total_income']:.2f}
- Total Expenses:     ${summary['total_expense']:.2f}
- Current Balance:    ${summary['balance']:.2f}
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

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
        )
    )
    # ↑ New API pattern:
    #   client.models.generate_content() instead of model.generate_content()
    #   config= replaces system_instruction in GenerativeModel()

    return response.text


# ─────────────────────────────────────────────────────
# FEATURE 2: AI Chat
# ─────────────────────────────────────────────────────

def chat_with_ai(
    user_message: str,
    transactions: List[Dict],
    summary: Dict,
    chat_history: Optional[List[Dict]] = None
) -> str:
    """Chat with AI about user's finances"""

    transactions_text = format_transactions_for_ai(transactions)

    # Build full context as system instruction
    system_with_context = f"""{SYSTEM_INSTRUCTION}

The user's current financial data:

SUMMARY:
- Income:   ${summary['total_income']:.2f}
- Expenses: ${summary['total_expense']:.2f}
- Balance:  ${summary['balance']:.2f}

TRANSACTIONS:
{transactions_text}

Answer their question using this specific data.
Reference their actual numbers when relevant.
Keep responses under 200 words."""

    # Build conversation history
    contents = []

    # Add chat history
    if chat_history:
        for msg in chat_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=content)]
                    )
                )
            elif role == 'assistant':
                contents.append(
                    types.Content(
                        role="model",
                        # ↑ Gemini uses "model" not "assistant"
                        parts=[types.Part(text=content)]
                    )
                )

    # Add current message
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_message)]
        )
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_with_context,
            temperature=0.7,
        )
    )

    return response.text


# ─────────────────────────────────────────────────────
# FEATURE 3: Category Advice
# ─────────────────────────────────────────────────────

def get_spending_advice(
    category: str,
    amount: float,
    total_income: float
) -> str:
    """Get AI advice for a specific spending category"""

    percentage = (amount / total_income * 100) if total_income > 0 else 0

    prompt = f"""
My spending on {category}:
- Amount spent:  ${amount:.2f}
- Total income:  ${total_income:.2f}
- Percentage:    {percentage:.1f}% of income

Please tell me:
1. Is ${amount:.2f} on {category} healthy?
2. What % of income should {category} be?
3. Give me 3 specific tips to optimize {category} spending

Keep response under 150 words. Be specific and practical.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
        )
    )

    return response.text