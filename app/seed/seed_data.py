from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import random


SEED_EMAILS = [
    {
        "from": {"name": "Sarah Chen", "email": "sarah.chen@techcorp.io"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "Q3 Product Roadmap — Review Required",
        "body": "Hi Mohit,\n\nI've finalized the Q3 product roadmap and would love your feedback before we present it to the leadership team on Friday.\n\nKey highlights:\n• AI-powered email categorization launch in August\n• Smart compose feature beta in September\n• Integration with third-party calendar apps\n\nPlease review the attached document and share your thoughts by EOD Wednesday.\n\nBest regards,\nSarah",
        "body_html": "<p>Hi Mohit,</p><p>I've finalized the Q3 product roadmap and would love your feedback before we present it to the leadership team on Friday.</p><p>Key highlights:</p><ul><li>AI-powered email categorization launch in August</li><li>Smart compose feature beta in September</li><li>Integration with third-party calendar apps</li></ul><p>Please review the attached document and share your thoughts by EOD Wednesday.</p><p>Best regards,<br>Sarah</p>",
        "snippet": "I've finalized the Q3 product roadmap and would love your feedback before we present it to...",
        "folder": "inbox",
        "labels": ["work", "important"],
        "is_read": False,
        "is_starred": True,
        "has_attachments": True,
        "attachments": [{"filename": "Q3_Roadmap_v2.pdf", "size": 2456000, "mime_type": "application/pdf"}],
        "hours_ago": 1,
    },
    {
        "from": {"name": "GitHub", "email": "notifications@github.com"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "[zynmail/frontend] Pull request #142: feat: dark mode implementation",
        "body": "A new pull request has been opened by @dev-alex:\n\n#142 feat: dark mode implementation\n\nThis PR adds comprehensive dark mode support including:\n- CSS custom properties for theme tokens\n- ThemeContext provider with localStorage persistence\n- Smooth transition animations between themes\n- Accessibility-compliant contrast ratios\n\n+847 -23 files changed\n\nReview requested from @mohit",
        "body_html": "<p>A new pull request has been opened by <strong>@dev-alex</strong>:</p><p><a href='#'>#142 feat: dark mode implementation</a></p><p>This PR adds comprehensive dark mode support including:</p><ul><li>CSS custom properties for theme tokens</li><li>ThemeContext provider with localStorage persistence</li><li>Smooth transition animations between themes</li><li>Accessibility-compliant contrast ratios</li></ul><p>+847 -23 files changed</p><p>Review requested from @mohit</p>",
        "snippet": "A new pull request has been opened by @dev-alex: #142 feat: dark mode implementation...",
        "folder": "inbox",
        "labels": ["github"],
        "is_read": False,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 2,
    },
    {
        "from": {"name": "Priya Sharma", "email": "priya@designstudio.co"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [{"name": "Design Team", "email": "design@zynmail.com"}],
        "bcc": [],
        "subject": "Updated Design System — Zynmail v2.0",
        "body": "Hey Mohit!\n\nExciting news — I've completed the updated design system for Zynmail v2.0. Here's what's new:\n\n🎨 New color palette with improved accessibility\n✨ Glassmorphism components library\n📱 Responsive breakpoints for all screen sizes\n🌙 Dark mode variants for every component\n\nThe Figma file has been shared with the team. Let me know when you'd like to do a design review session.\n\nCheers,\nPriya",
        "body_html": "<p>Hey Mohit!</p><p>Exciting news — I've completed the updated design system for Zynmail v2.0. Here's what's new:</p><ul><li>🎨 New color palette with improved accessibility</li><li>✨ Glassmorphism components library</li><li>📱 Responsive breakpoints for all screen sizes</li><li>🌙 Dark mode variants for every component</li></ul><p>The Figma file has been shared with the team. Let me know when you'd like to do a design review session.</p><p>Cheers,<br>Priya</p>",
        "snippet": "Exciting news — I've completed the updated design system for Zynmail v2.0. Here's what's new...",
        "folder": "inbox",
        "labels": ["design"],
        "is_read": True,
        "is_starred": True,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 5,
    },
    {
        "from": {"name": "AWS Notifications", "email": "no-reply@aws.amazon.com"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "Your AWS bill for July 2026 is available",
        "body": "Hello,\n\nYour AWS bill for the billing period July 1 - July 25, 2026 is now available.\n\nTotal charges: $127.43\n\nTop services:\n• Amazon EC2: $64.20\n• Amazon S3: $23.15\n• Amazon RDS: $31.08\n• Other: $9.00\n\nSign in to the AWS Management Console to view your full bill.\n\nThank you for using AWS.",
        "body_html": "<p>Hello,</p><p>Your AWS bill for the billing period July 1 - July 25, 2026 is now available.</p><p><strong>Total charges: $127.43</strong></p><p>Top services:</p><ul><li>Amazon EC2: $64.20</li><li>Amazon S3: $23.15</li><li>Amazon RDS: $31.08</li><li>Other: $9.00</li></ul><p>Sign in to the AWS Management Console to view your full bill.</p>",
        "snippet": "Your AWS bill for the billing period July 1 - July 25, 2026 is now available. Total charges: $127.43",
        "folder": "inbox",
        "labels": ["billing"],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 8,
    },
    {
        "from": {"name": "Alex Rivera", "email": "alex.r@zynmail.com"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "Weekend hackathon — who's in?",
        "body": "Hey Mohit,\n\nThinking of organizing a weekend hackathon this Saturday. The theme would be 'AI + Productivity Tools'.\n\nPlan:\n- Start at 10 AM, code until 6 PM\n- Pizza and drinks provided 🍕\n- Demo and voting at the end\n- Winner gets bragging rights + a Steam gift card\n\nWe already have 8 people confirmed. Want to join?\n\n— Alex",
        "body_html": "<p>Hey Mohit,</p><p>Thinking of organizing a weekend hackathon this Saturday. The theme would be 'AI + Productivity Tools'.</p><p>Plan:</p><ul><li>Start at 10 AM, code until 6 PM</li><li>Pizza and drinks provided 🍕</li><li>Demo and voting at the end</li><li>Winner gets bragging rights + a Steam gift card</li></ul><p>We already have 8 people confirmed. Want to join?</p><p>— Alex</p>",
        "snippet": "Thinking of organizing a weekend hackathon this Saturday. The theme would be 'AI + Productivity...",
        "folder": "inbox",
        "labels": ["social"],
        "is_read": False,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 12,
    },
    {
        "from": {"name": "Stripe", "email": "receipts@stripe.com"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "Your receipt from Zynmail Pro",
        "body": "Payment receipt\n\nAmount paid: $29.00\nDate: July 25, 2026\nPayment method: Visa ending in 4242\n\nDescription: Zynmail Pro — Monthly subscription\n\nThank you for your payment. If you have questions, contact support@zynmail.com.",
        "body_html": "<h3>Payment receipt</h3><p><strong>Amount paid:</strong> $29.00</p><p><strong>Date:</strong> July 25, 2026</p><p><strong>Payment method:</strong> Visa ending in 4242</p><p><strong>Description:</strong> Zynmail Pro — Monthly subscription</p><p>Thank you for your payment.</p>",
        "snippet": "Payment receipt — Amount paid: $29.00 — Zynmail Pro Monthly subscription",
        "folder": "inbox",
        "labels": ["receipts"],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 24,
    },
    {
        "from": {"name": "Dr. Maya Patel", "email": "maya.patel@university.edu"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "Re: Research collaboration on LLM-powered email agents",
        "body": "Hi Mohit,\n\nThank you for reaching out about the research collaboration. I've been following Zynmail's progress and I think there's a great opportunity to work together on LLM-powered email agents.\n\nMy lab has been working on:\n1. Intent classification for email actions\n2. Context-aware response generation\n3. Privacy-preserving email summarization\n\nWould you be available for a call next week to discuss further?\n\nBest,\nDr. Maya Patel\nProfessor of Computer Science",
        "body_html": "<p>Hi Mohit,</p><p>Thank you for reaching out about the research collaboration. I've been following Zynmail's progress and I think there's a great opportunity to work together on LLM-powered email agents.</p><p>My lab has been working on:</p><ol><li>Intent classification for email actions</li><li>Context-aware response generation</li><li>Privacy-preserving email summarization</li></ol><p>Would you be available for a call next week to discuss further?</p><p>Best,<br>Dr. Maya Patel<br>Professor of Computer Science</p>",
        "snippet": "Thank you for reaching out about the research collaboration. I've been following Zynmail's...",
        "folder": "inbox",
        "labels": ["important", "research"],
        "is_read": False,
        "is_starred": True,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 28,
    },
    {
        "from": {"name": "Mohit", "email": "mohit@zynmail.com"},
        "to": [{"name": "Team", "email": "team@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "Sprint planning notes — Week 30",
        "body": "Team,\n\nHere are the key items from today's sprint planning:\n\n1. Complete Gmail clone UI (frontend) — Priority: HIGH\n2. MongoDB integration — Priority: HIGH\n3. Email compose and send flow — Priority: MEDIUM\n4. AI summarization prototype — Priority: LOW\n\nLet's sync up on progress Wednesday.\n\n— Mohit",
        "body_html": "<p>Team,</p><p>Here are the key items from today's sprint planning:</p><ol><li>Complete Gmail clone UI (frontend) — Priority: HIGH</li><li>MongoDB integration — Priority: HIGH</li><li>Email compose and send flow — Priority: MEDIUM</li><li>AI summarization prototype — Priority: LOW</li></ol><p>Let's sync up on progress Wednesday.</p><p>— Mohit</p>",
        "snippet": "Here are the key items from today's sprint planning: 1. Complete Gmail clone UI...",
        "folder": "sent",
        "labels": ["work"],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 48,
    },
    {
        "from": {"name": "Mohit", "email": "mohit@zynmail.com"},
        "to": [{"name": "Dr. Maya Patel", "email": "maya.patel@university.edu"}],
        "cc": [],
        "bcc": [],
        "subject": "Research collaboration on LLM-powered email agents",
        "body": "Dear Dr. Patel,\n\nI hope this email finds you well. I'm Mohit, the founder of Zynmail — an AI-powered mailing platform.\n\nI recently read your paper on context-aware NLP systems and I believe there's a strong synergy between your research and what we're building at Zynmail.\n\nWould you be open to discussing a potential research collaboration?\n\nBest regards,\nMohit",
        "body_html": "<p>Dear Dr. Patel,</p><p>I hope this email finds you well. I'm Mohit, the founder of Zynmail — an AI-powered mailing platform.</p><p>I recently read your paper on context-aware NLP systems and I believe there's a strong synergy between your research and what we're building at Zynmail.</p><p>Would you be open to discussing a potential research collaboration?</p><p>Best regards,<br>Mohit</p>",
        "snippet": "I hope this email finds you well. I'm Mohit, the founder of Zynmail...",
        "folder": "sent",
        "labels": [],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 72,
    },
    {
        "from": {"name": "Mohit", "email": "mohit@zynmail.com"},
        "to": [{"name": "Investors", "email": "investors@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "Zynmail — Investor update draft",
        "body": "Draft — Investor Update Q3 2026\n\n[TODO: Add metrics]\n[TODO: Add growth chart]\n[TODO: Add product screenshots]\n\nKey highlights:\n- Launched AI email categorization\n- 150% MoM user growth\n- $2.3M ARR milestone",
        "body_html": "",
        "snippet": "Draft — Investor Update Q3 2026. Key highlights: Launched AI email categorization...",
        "folder": "drafts",
        "labels": ["important"],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 96,
    },
    {
        "from": {"name": "LinkedIn", "email": "notifications@linkedin.com"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "You have 5 new connection requests",
        "body": "You have new connection requests:\n\n1. Jane Smith — Senior PM at Google\n2. Raj Kumar — ML Engineer at Meta\n3. Lisa Wang — Founder at StartupXYZ\n4. Tom Anderson — VC at Sequoia\n5. Maria Garcia — Designer at Figma\n\nView and respond to your requests on LinkedIn.",
        "body_html": "",
        "snippet": "You have new connection requests: Jane Smith — Senior PM at Google, Raj Kumar — ML Engineer...",
        "folder": "inbox",
        "labels": ["social"],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 36,
    },
    {
        "from": {"name": "Security Alert", "email": "security@zynmail.com"},
        "to": [{"name": "Mohit", "email": "mohit@zynmail.com"}],
        "cc": [],
        "bcc": [],
        "subject": "New sign-in from Chrome on Linux",
        "body": "We noticed a new sign-in to your Zynmail account.\n\nDevice: Chrome on Linux\nLocation: Mumbai, India\nTime: July 25, 2026, 5:30 PM IST\nIP: 103.xx.xx.xx\n\nIf this was you, no action is needed.\nIf not, please secure your account immediately.",
        "body_html": "",
        "snippet": "We noticed a new sign-in to your Zynmail account. Device: Chrome on Linux...",
        "folder": "inbox",
        "labels": ["security"],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "hours_ago": 3,
    },
]


async def seed_database(db: AsyncIOMotorDatabase):
    """Seed the database with realistic demo emails."""
    # Check if already seeded
    count = await db.emails.count_documents({})
    if count > 0:
        print(f"📧 Database already has {count} emails, skipping seed")
        return

    now = datetime.now(timezone.utc)

    for email_data in SEED_EMAILS:
        hours_ago = email_data.pop("hours_ago", 0)
        email_data["timestamp"] = now - timedelta(hours=hours_ago)
        email_data["thread_id"] = None
        email_data["in_reply_to"] = None

    await db.emails.insert_many(SEED_EMAILS)
    print(f"🌱 Seeded {len(SEED_EMAILS)} demo emails")

    # Create indexes
    await db.emails.create_index([("folder", 1)])
    await db.emails.create_index([("is_starred", 1)])
    await db.emails.create_index([("is_read", 1)])
    await db.emails.create_index([("timestamp", -1)])
    await db.emails.create_index([
        ("subject", "text"),
        ("body", "text"),
        ("from.name", "text"),
    ])
    print("📇 Created database indexes")
