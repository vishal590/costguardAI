# How to Write the Builder Center Article

**Purpose:** One place for how to write your AWS 10,000 AIdeas Builder Center article. Use this when you start drafting.  
**Deadline (per selection email):** March 13, 2026 **8:00 PM UTC** (12:00 PM PT | 4:00 AM IST Mar 14).  
**Source:** [SEMI_FINALIST_SELECTION_EMAIL.md](./SEMI_FINALIST_SELECTION_EMAIL.md) – sections, title format, tags, deadlines.  
**Related:** [SEMI-FINALIST-PHASE.md](./SEMI-FINALIST-PHASE.md), [ARTICLE_DRAFT.md](./ARTICLE_DRAFT.md) (copy-paste content), [HACKATHON_WINNING_STRATEGY.md](../HACKATHON_WINNING_STRATEGY.md) (strategy)

---

## Official guidelines (from email)

When writing your article, include:

1. **Sections:** App category · My vision · Why this matters · How I built this · Demo · What I learned  
2. **Cover image** – something that captures attention.  
3. **Article title** – use: **"AIdeas: [your project or app name]"** → for us: **AIdeas: CostGuard AI**  
4. **Tags:** 1) `#aideas-2025`, 2) your app category tag (e.g. `#commercial-solutions`), 3) your region tag (`#EMEA`, `#NAMER`, `#APJC`, `#LATAM`, `#GCR`, `#ANZ`).

Demo: screenshots **or** a video under 5 minutes (e.g. YouTube, then embed with Insert YouTube embed).

---

## 1. Title, tags, and formatting (do first)

| Item | What to use |
|------|-------------|
| **Title** | `AIdeas: CostGuard AI` (exact format from official email) |
| **Cover image** | Required. Use something that catches attention (e.g. dashboard or demo screenshot). |
| **Competition tag** | `#aideas-2025` (mandatory) |
| **App category tag** | `#commercial-solutions` (CostGuard AI) |
| **Region tag** | One of `#EMEA`, `#NAMER`, `#APJC`, `#LATAM`, `#GCR`, `#ANZ` (pick your region) |

**Where to publish:** [AWS Builder Center](https://aws.amazon.com/builders-center/). After publishing, share/link your article in the [10,000 AIdeas competition space](https://builder.aws.com/connect/space/3a92613a-ce41-30a7-bc0d-6067611fbd09/10000-aideas-competition) so it can get likes.

### ⚠️ Create an Article, not a Post (from competition space)

The AWS team has clarified: **do not create a "post" inside the competition space** as your final submission. That won’t give you enough space or proper tagging.

**Correct way to publish:**
1. On any **Builder Center** page, click the **"+"** icon in the **top right** (next to search, notifications, profile).
2. In the **Create** menu, choose **"Article"** (not "Post" or "Wish").
3. Write your full article there. You get room for screenshots/video, full text, and the required tags.
4. After publishing, share or link your article in the 10,000 AIdeas Competition space so people can find it and like it.

*Source: “Confusion about posts vs. articles” (Ben Fowler, AWS) in the 10,000 AIdeas Competition space.*

---

## 2. Required sections (in order)

Your article **must** include these six sections. The Terms also require: **development process**, **technical architecture**, and **key learnings** (fold these into “How I Built This” and “What I Learned”).

### 1) App Category

- State: **Commercial Solutions**.
- One short sentence is enough.

### 2) My Vision

- **What your idea is** and **what you built**.
- Be clear about the **problem** (e.g. AWS costs unpredictable, 24‑hour delay, manual optimization).
- Explain your **solution** (CostGuardAI: real-time visibility, prevention, autonomous optimization).
- Optional: align with your original pitch in [FORM-FIELD-RESPONSES.md](./FORM-FIELD-RESPONSES.md) (Big Idea, Vision).

### 3) Why This Matters

- Why it matters to **people / businesses**.
- Tie to **Commercial Solutions**: SMBs, startups, teams that want to control AWS spend.
- Real-world impact: e.g. 20–30% savings, no manual drudgery, autonomous safety.

### 4) How I Built This

- **Technical approach** and **architecture** (high-level: phases, APIs, Lambda, Bedrock, EventBridge, etc.).
- **AWS services used** – list with short justification and how each is used (see template below).
- **Kiro usage** – e.g. “Used Kiro for 70%+ of development” and where (design, code, tests, docs).
- **Development milestones** – e.g. Phase 1→6, autonomous loop, frontend.
- **Key learnings** – what you learned technically and in the process (can also go in “What I Learned”).

**Must include:** Development process, technical architecture, key learnings (Terms requirement).

### 5) Demo

- **Screenshots** of the app **or** a **video under 5 minutes** (e.g. YouTube, then embed in Builder Center).
- **Show:** Dashboard, “Run autonomous optimization,” phases (Analyze→Decide→Act→Verify→Learn), progress/savings, and optionally Cost/Forecast/Advisor.
- **Optional:** Before/after cost comparison, metrics (e.g. 5.26s execution, 20–30% savings).

### 6) What I Learned

- What you learned during the project.
- Challenges you overcame, technical learnings, Kiro and AWS insights, process takeaways.

---

## 3. Suggested article structure (with hooks)

Use this flow so the article is easy to read and judges/voters see the impact quickly.

1. **Hook (first ~100 words)**  
   Relatable problem (e.g. “Your AWS bill just doubled. Again.”) → introduce CostGuardAI and autonomous optimization.

2. **Problem statement**  
   Reactive cost management, 24‑hour delay, manual optimization, tools that only suggest and don’t act.

3. **Solution overview**  
   Conversational advisor + **autonomous optimization** (learns and acts), real-time estimation, safety guards and rollback.

4. **How I built this**  
   Architecture (phases, 5-phase loop), AWS services list with justification, Kiro usage, key learnings.

5. **Demo & results**  
   Video or screenshots, metrics (5.26s run, 20–30% savings, 1,621 tests, ~$4/month).

6. **AWS services used**  
   Table or list: service name, purpose, justification, Free Tier, expected cost. End with **expected running costs** and **resource optimization** (e.g. stay within Free Tier).

7. **Team & call to action**  
   Team name, “Built with Kiro,” invite to try the demo and vote.

Full structure and messaging details: [HACKATHON_WINNING_STRATEGY.md – Article Strategy](../HACKATHON_WINNING_STRATEGY.md#4-article-strategy-march-13-deadline).

---

## 4. AWS services section (template)

List each service with:

- **Purpose** – what it’s used for.
- **Justification** – why this service (cost, scale, Free Tier).
- **Usage** – how it’s used in CostGuardAI.
- **Free Tier** – relevant limits.
- **Expected cost** – e.g. $0 or ~$X/month.

**Example (short):**

```text
1. **Amazon Lambda** – API and business logic. Fits Free Tier, serverless. Handles cost, forecast, prevention, advisor, autonomous APIs. Free Tier: 1M requests/month. Expected: $0.
2. **Amazon Bedrock** – Forecasting and advisor (Nova Lite). Managed AI, pay-per-use. Used for cost forecast and natural-language advisor. Expected: within Free Tier / low cost.
...
```

Use your real list (e.g. Lambda, API Gateway, DynamoDB, EventBridge, S3, Bedrock, Cost Explorer, CloudWatch, SNS, etc.) and keep each to 1–3 lines unless you want one “hero” service explained in more detail. End with **resource optimization** and **total expected running costs** (~$4/month).

---

## 5. Terms, quality, and common mistakes

- **Writing:** Clear, concise, good headings, professional tone, no spelling/grammar errors.
- **Technical:** Accurate AWS and Free Tier info, realistic costs, working demo.
- **Visuals:** Good screenshots or clear video, optional diagram (e.g. 5-phase loop).
- **Terms (mandatory):** Article MUST describe **development process**, **technical architecture**, and **key learnings** (fold into "How I Built This" and "What I Learned").
- **Avoid:** Exceeding Free Tier; underplaying Kiro; missing demo; incomplete AWS services list; vague value proposition; wrong or missing tags/title; fake accounts or bots to inflate likes (disqualification).

More do’s and don’ts: *(Requirements merged into this doc; see section 5 above.)*.

---

## 6. Where everything lives in this repo

| Need | Doc |
|------|-----|
| Official deadlines, credits, article rules | [SEMI_FINALIST_SELECTION_EMAIL.md](./SEMI_FINALIST_SELECTION_EMAIL.md) |
| Semi-finalist tasks, build + article + likes | [SEMI-FINALIST-PHASE.md](./SEMI-FINALIST-PHASE.md) |
| Copy-paste article (title, description, body) | [ARTICLE_DRAFT.md](./ARTICLE_DRAFT.md) |
| Submission requirements (initial + semi-finalist) | [requirements.md](./requirements.md) |
| Hook, structure, engagement | [HACKATHON_WINNING_STRATEGY.md](../HACKATHON_WINNING_STRATEGY.md) |
| Original pitch (vision, game plan) | [FORM-FIELD-RESPONSES.md](./FORM-FIELD-RESPONSES.md) |
| Checklist before submit | [checklist.md](./checklist.md) |
| Demo screenshots order and captions | [DEMO_SCREENSHOTS_AND_CAPTIONS.md](./DEMO_SCREENSHOTS_AND_CAPTIONS.md) |

---

## 7. Quick start

1. **Ready-to-paste draft:** [ARTICLE_DRAFT.md](./ARTICLE_DRAFT.md) has Title, Description (for the form), and full Body in Markdown—copy into the Builder Center "Create an article" form, then add cover image and tags.
2. Set **title** = `AIdeas: CostGuard AI`, **tags** = `#aideas-2025`, `#commercial-solutions`, and your **region**.
2. Add a **cover image**.
3. Draft the **six required sections** in order (App Category → My Vision → Why This Matters → How I Built This → Demo → What I Learned).
4. In “How I Built This,” include **development process**, **technical architecture**, **AWS services** (with template above), **Kiro**, and **key learnings**.
5. Record or pick **demo** (video &lt;5 min or screenshots); embed or insert in **Demo**.
6. Proofread and run through [checklist.md](./checklist.md); publish by **March 13, 2026 8:00 PM UTC (12:00 PM PT)**, then share in the competition space to get likes. Keep your Builder Center profile up to date. Do not use fake accounts or bots to inflate likes—disqualification.

**Last updated:** March 2026
