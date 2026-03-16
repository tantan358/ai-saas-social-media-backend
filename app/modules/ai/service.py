from typing import Dict, Any, List, Optional, TYPE_CHECKING
from app.config import settings
import requests
import json
import re

if TYPE_CHECKING:
    from app.modules.campaigns.schemas import GenerationOptions

from app.modules.campaigns.constants import ALLOWED_CHANNELS


# Words that indicate wrong language (simple heuristic)
ENGLISH_DOMINANT = re.compile(r"\b(the|and|is|are|was|were|have|has|had|for|with|this|that|you|your|will|can)\b", re.I)
SPANISH_DOMINANT = re.compile(r"\b(el|la|los|las|un|una|de|que|en|es|por|con|para|al|lo|como|más|pero|sus|le|ya|o|fue|este|sí|porque|esta|entre|cuando|muy|sin|sobre|también|me|hasta|hay|donde|han|quien|desde|todo|nos|durante|estados|todos|uno|les|ni|contra|otros|ese|eso|ante|ellos|e|esto|mí|antes|algunos|qué|unos|yo|otro|otras|otra|él|tanto|esa|estos|mucho|quienes|nada|ser|muchos|cuál|sea|poco|ella|están|estas|algunas|algo|nosotros)\b", re.I)


def validate_content_language(content: str, expected_language: str) -> None:
    """Raise ValueError if content appears to be in the wrong language."""
    if not content or not content.strip():
        return
    content_lower = content.lower()
    if expected_language == "es":
        en_count = len(ENGLISH_DOMINANT.findall(content_lower))
        if en_count >= 3:  # dominant English
            raise ValueError("Content appears to be in English; campaign language is Spanish (ES).")
    elif expected_language == "en":
        es_count = len(SPANISH_DOMINANT.findall(content_lower))
        if es_count >= 3:  # dominant Spanish
            raise ValueError("Content appears to be in Spanish; campaign language is English (EN).")


# -----------------------------------------------------------------------------
# Channel distribution algorithm (monthly post generation)
# -----------------------------------------------------------------------------
# Inputs come from GenerationOptions (channels list and posts_per_channel_per_week).
# Channels are any supported identifiers from ALLOWED_CHANNELS; the generator
# does not assume a fixed set. Each post has an explicit "platform" field set
# to one of options.channels. Order of posts follows _week_posts_spec: all
# slots for channel A, then all for channel B, etc.
# -----------------------------------------------------------------------------


def _week_posts_spec(options: "GenerationOptions") -> List[tuple]:
    """
    Return for one week a list of (platform, slot_key) in order: all posts for
    each channel in options.channels (with compressed slots per channel).
    Supports up to 7 posts per channel; total per week = sum(posts_per_channel_per_week).
    """
    out: List[tuple] = []
    for channel in options.channels:
        n = options.posts_per_channel_per_week.get(channel, 1)
        n = max(1, min(7, n))
        slot_indices = _get_weekly_slot_indices(n)
        for i in range(n):
            slot_key = WEEKLY_STRUCTURE_SLOTS[slot_indices[i]]
            out.append((channel, slot_key))
    return out


def _content_by_length(base: str, length: str, language: str) -> str:
    """Expand or shorten placeholder for content_length (short/medium/long). Mock uses base; API gets instruction."""
    if length == "short":
        return base.split(".")[0].strip() + "." if "." in base else base[:120]
    if length == "long":
        return base + " " + (base.split(".")[0] if "." in base else base[:80])
    return base


# -----------------------------------------------------------------------------
# Weekly planning structure (structured campaign themes)
# -----------------------------------------------------------------------------
# Canonical 7-slot week (posts_per_week = 7):
#   Day 1 – Education    Slot 0
#   Day 2 – Lead attraction  Slot 1
#   Day 3 – Product benefit  Slot 2
#   Day 4 – Use case     Slot 3
#   Day 5 – Brand authority  Slot 4
#   Day 6 – Service promotion  Slot 5
#   Day 7 – Conversion / CTA  Slot 6
# For n < 7 we compress: pick n slots spread across the funnel (see below).
# Each post aligns with one slot; slots map to campaign_goal_mix where possible.
# -----------------------------------------------------------------------------

WEEKLY_STRUCTURE_SLOTS = [
    "education",           # 0 – awareness, thought_leadership
    "lead_attraction",     # 1 – leads
    "product_benefit",     # 2 – engagement, brand_loyalty
    "use_case",            # 3 – engagement, traffic
    "brand_authority",    # 4 – thought_leadership, brand_loyalty
    "service_promotion",   # 5 – traffic, conversions
    "conversion_cta",      # 6 – conversions, sales
]

# Slot -> suggested campaign_goal_mix alignment (for variety and goal alignment)
SLOT_TO_GOALS: Dict[str, List[str]] = {
    "education": ["awareness", "thought_leadership"],
    "lead_attraction": ["leads", "traffic"],
    "product_benefit": ["engagement", "brand_loyalty"],
    "use_case": ["engagement", "traffic"],
    "brand_authority": ["thought_leadership", "brand_loyalty"],
    "service_promotion": ["traffic", "conversions"],
    "conversion_cta": ["conversions", "sales"],
}

# Slot -> content objective (for objective_mode=mixed storage)
SLOT_TO_OBJECTIVE: Dict[str, str] = {
    "education": "education",
    "lead_attraction": "lead_generation",
    "product_benefit": "product_promotion",
    "use_case": "positioning",
    "brand_authority": "brand_authority",
    "service_promotion": "product_promotion",
    "conversion_cta": "conversion",
}

WEEKDAY_ORDER = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _compute_objectives_for_plan(options: "GenerationOptions") -> List[str]:
    """
    Return content_objective for each post in the same order as generated (week 1..4, then spec order).
    Used for mixed / by_day / by_post; result length = 4 * len(_week_posts_spec(options)).
    """
    spec = _week_posts_spec(options)
    total_per_week = len(spec)
    total_posts = 4 * total_per_week
    objectives: List[str] = []
    for i in range(total_posts):
        slot_in_week = i % total_per_week
        platform, slot_key = spec[slot_in_week]
        mode = getattr(options, "objective_mode", "mixed") or "mixed"
        if mode == "mixed":
            obj = SLOT_TO_OBJECTIVE.get(slot_key, "education")
        elif mode == "by_day":
            by_day = getattr(options, "objective_by_day", None) or {}
            day = WEEKDAY_ORDER[slot_in_week] if slot_in_week < len(WEEKDAY_ORDER) else WEEKDAY_ORDER[-1]
            obj = by_day.get(day, "education")
        else:  # by_post
            by_post = getattr(options, "objective_by_post", None) or ["education"]
            obj = by_post[i % len(by_post)]
        objectives.append(obj)
    return objectives


def _get_weekly_slot_indices(n_posts: int) -> List[int]:
    """
    Return which of the 7 canonical slots to use when generating n_posts (e.g. per channel).
    Compresses the full week structure logically: spans funnel from education to CTA.
    n_posts in [1, 7]; result length = n_posts.
    """
    if n_posts >= 7:
        return list(range(7))
    if n_posts <= 1:
        return [0]
    # Spread n_posts across indices 0..6 so we keep first (Education) and last (CTA)
    # and fill middle proportionally. Linear spacing: 0, ..., 6 included when possible.
    indices: List[int] = []
    for i in range(n_posts):
        # i=0 -> 0, i=n_posts-1 -> 6, else proportional
        idx = round(i * (6.0 / max(n_posts - 1, 1)))
        indices.append(min(idx, 6))
    # Dedupe preserving order (e.g. n=2 -> [0,6])
    seen: set = set()
    out: List[int] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            out.append(idx)
    # If we collapsed duplicates, pad from full 7 and take first n
    while len(out) < n_posts and len(out) < 7:
        for idx in range(7):
            if idx not in seen and len(out) < n_posts:
                out.append(idx)
                seen.add(idx)
                break
        else:
            break
    return out[:n_posts]


# Title/angle variants per slot (ES/EN) for variety across weeks; avoid repeating same idea in same week.
THEME_TITLES: Dict[str, Dict[str, List[str]]] = {
    "education": {
        "es": ["Aprende con nosotros", "Formación que suma", "Conocimiento práctico", "Claves del sector"],
        "en": ["Learn with us", "Practical knowledge", "Industry insights", "Key takeaways"],
    },
    "lead_attraction": {
        "es": ["Atrae a tu audiencia ideal", "Contenido que genera interés", "Leads de calidad", "Conecta con más clientes"],
        "en": ["Attract your ideal audience", "Content that generates interest", "Quality leads", "Connect with more clients"],
    },
    "product_benefit": {
        "es": ["Beneficios que marcan la diferencia", "Por qué elegirnos", "Valor para tu negocio", "Ventajas clave"],
        "en": ["Benefits that make the difference", "Why choose us", "Value for your business", "Key advantages"],
    },
    "use_case": {
        "es": ["Casos de uso reales", "Así lo usan nuestros clientes", "Aplicación práctica", "Ejemplos que inspiran"],
        "en": ["Real use cases", "How our clients use it", "Practical application", "Examples that inspire"],
    },
    "brand_authority": {
        "es": ["Autoridad de marca", "Expertos en el sector", "Referencia del mercado", "Liderazgo de opinión"],
        "en": ["Brand authority", "Industry experts", "Market reference", "Thought leadership"],
    },
    "service_promotion": {
        "es": ["Promoción de servicios", "Oferta para ti", "Descubre nuestros servicios", "Soluciones a medida"],
        "en": ["Service promotion", "An offer for you", "Discover our services", "Tailored solutions"],
    },
    "conversion_cta": {
        "es": ["Llamada a la acción", "Da el siguiente paso", "Contáctanos hoy", "Actúa ahora"],
        "en": ["Call to action", "Take the next step", "Contact us today", "Act now"],
    },
}


def _pick_title_for_slot(slot_key: str, language: str, week: int, slot_index_in_week: int) -> str:
    """Pick a title variant for this slot so we vary by week and avoid repeating in same week."""
    by_lang = THEME_TITLES.get(slot_key, {}).get(language, THEME_TITLES["education"][language])
    # Use (week, slot_index_in_week) to pick variant without repeating in same week
    idx = (week * 7 + slot_index_in_week) % max(len(by_lang), 1)
    return by_lang[idx]


# -----------------------------------------------------------------------------
# AI prompt templates for monthly content generation (API)
# -----------------------------------------------------------------------------

def _build_monthly_generation_system_prompt(
    lang_label: str,
    language_code: str,
    channels_str: str,
    distribution_strategy: str,
    posts_per_channel_per_week: Dict[str, int],
    total_per_week: int,
    total_posts: int,
    week_structure_desc: str,
    goals_str: str,
    length_instruction: str,
    call_to_action_required: bool,
    objective_instruction: Optional[str] = None,
    example_platform: Optional[str] = None,
) -> str:
    cta_rule = (
        " Include a clear, varied call-to-action (CTA) in every post."
        if call_to_action_required
        else " For the Conversion/CTA slot only, include a soft or strong CTA; other posts may omit CTA."
    )
    per_channel_desc = "; ".join(
        f"{ch}: {n} posts/week" for ch, n in sorted(posts_per_channel_per_week.items())
    )
    return f"""You are an expert social media content planner. Your task is to generate a full monthly content plan.

## CRITICAL RULES (must follow)

1. **Exact volume per channel**: Each week must have exactly these posts per platform: {per_channel_desc}. Total per week = {total_per_week}. For 4 weeks, total posts = {total_posts}. Do not output fewer or more.

2. **Channels**: Use only these platforms: {channels_str}. Each channel gets its own count per week (up to 7 per channel). Multiple posts per channel in the same week are required when the count for that channel is > 1.

3. **Marketing goals**: Campaign goals are: {goals_str}. Vary the goals across posts: each post must have a single **campaign_goal_tag** from this list. Rotate goals so the mix is balanced over the month; do not cluster the same goal in one week.

4. **No repetition**: Do not repeat the same theme, title, or core idea within the same week. Vary titles and angles across posts and across weeks. Every post must feel distinct.

5. **Language**: All copy (title, content, hashtags) must be strictly in {lang_label}. Do not mix languages.

6. **Content length**: Each post body must be {length_instruction}. Respect this precisely.

7. **CTA**:{cta_rule}

8. **Links**: If you cannot determine an appropriate link for a post, set "link" to "" or null. Only suggest a link when it clearly fits the post (e.g. landing page, signup, product).

## Weekly structure (apply every week in this order)

{week_structure_desc}

Each post must match its slot theme (Education, Lead attraction, etc.). Post 1 = first slot, Post 2 = second slot, and so on.
""" + (
    f"""

9. **Content objective**: {objective_instruction}
""" if objective_instruction else ""
) + f"""

## Output format

Return a single JSON array of post objects. Each object must have these keys:
- week_number (integer 1-4)
- platform (string: one of {channels_str})
- title (string, short)
- content (string, post body in {lang_label}, {length_instruction})
- hashtags (array of strings, optional; 3-5 relevant hashtags)
- link (string or null; empty string or null if no link)
- campaign_goal_tag (string; one of: {goals_str})

Example shape for one post (use one of the platform names from the list above):
{{\"week_number\": 1, \"platform\": \"{example_platform or "linkedin"}\", \"title\": \"...\", \"content\": \"...\", \"hashtags\": [\"#Tag1\", \"#Tag2\"], \"link\": \"\", \"campaign_goal_tag\": \"awareness\"}}

Generate the full array of {total_posts} posts. No commentary, only the JSON array."""


def _build_monthly_generation_user_prompt(campaign_name: str, description: str, channels_str: str) -> str:
    return f"""Campaign name: {campaign_name}

Campaign description: {description}

Generate the complete monthly plan. Return only a JSON array of post objects with keys: week_number, platform, title, content, hashtags, link, campaign_goal_tag. Use only platforms: {channels_str}."""


class AIService:
    """AI service for generating campaign plans and posts."""

    @staticmethod
    def generate_monthly_plan_posts(
        campaign_name: str,
        description: str,
        options: "GenerationOptions",
    ) -> List[Dict[str, Any]]:
        """
        Generate structured plan for 4 weeks; posts per week and channels from options.
        Each post: title, platform (from options.channels), content.
        Supports multiple posts per channel. Uses AI_PROVIDER env or mock if no key.
        """
        if settings.AI_API_KEY and settings.AI_PROVIDER:
            return AIService._generate_via_api(campaign_name, description, options)
        return AIService._generate_mock(campaign_name, description, options)

    @staticmethod
    def _generate_mock(
        campaign_name: str,
        description: str,
        options: "GenerationOptions",
    ) -> List[Dict[str, Any]]:
        """
        Mock: 4 weeks, per-channel limits (up to 7 per channel, 14 total/week).
        Each channel gets its own compressed weekly structure; titles/variety by slot.
        """
        posts = []
        language = options.language
        spec = _week_posts_spec(options)
        objectives = _compute_objectives_for_plan(options)

        for week in range(1, 5):
            week_0 = week - 1
            for post_idx, (platform, slot_key) in enumerate(spec):
                global_idx = (week - 1) * len(spec) + post_idx
                title = _pick_title_for_slot(slot_key, language, week_0, post_idx)

                if language == "es":
                    body = (
                        f"Este contenido forma parte de la campaña «{campaign_name}». "
                        f"{description or 'Contenido de valor para nuestra audiencia.'}"
                    )
                else:
                    body = (
                        f"This content is part of the «{campaign_name}» campaign. "
                        f"{description or 'Valuable content for our audience.'}"
                    )
                content = f"🎯 {title}\n\n{body}\n\n#MarketingDigital #SocialMedia"

                # CTA: always strong on conversion_cta slot; otherwise when call_to_action_required
                add_cta = options.call_to_action_required or (slot_key == "conversion_cta")
                if add_cta:
                    cta_es = " ¿Te gustaría saber más? Contáctanos."
                    cta_en = " Want to learn more? Get in touch."
                    content = content.rstrip() + (cta_es if language == "es" else cta_en)
                content = _content_by_length(content, options.content_length, language)

                # Align campaign_goal_tag with slot (match API response shape)
                slot_goals = SLOT_TO_GOALS.get(slot_key, ["engagement"])
                goal_tag = next(
                    (g for g in slot_goals if g in (options.campaign_goal_mix or [])),
                    options.campaign_goal_mix[0] if options.campaign_goal_mix else "engagement",
                )
                if not isinstance(goal_tag, str):
                    goal_tag = options.campaign_goal_mix[0] if options.campaign_goal_mix else "engagement"

                posts.append({
                    "week_number": week,
                    "title": title,
                    "platform": platform,
                    "content": content,
                    "hashtags": ["#MarketingDigital", "#SocialMedia"],
                    "link": "",
                    "campaign_goal_tag": goal_tag,
                    "content_objective": objectives[global_idx] if global_idx < len(objectives) else "education",
                })
        return posts

    @staticmethod
    def _generate_via_api(
        campaign_name: str,
        description: str,
        options: "GenerationOptions",
    ) -> List[Dict[str, Any]]:
        """Call OpenAI-style API to generate 4 weeks of posts; prompt enforces per-channel volume and structured output."""
        language = options.language
        lang_label = "Spanish" if language == "es" else "English"
        channels_str = ", ".join(options.channels)
        length_instruction = {
            "short": "1-2 short sentences only",
            "medium": "2-4 sentences",
            "long": "4-6 sentences or short paragraphs",
        }.get(options.content_length, "2-4 sentences")
        per_channel = options.posts_per_channel_per_week
        total_per_week = sum(per_channel.values())
        total_posts = 4 * total_per_week
        slot_names = [
            "Education", "Lead attraction", "Product benefit", "Use case",
            "Brand authority", "Service promotion", "Conversion / CTA",
        ]
        parts = []
        for ch in options.channels:
            n = per_channel.get(ch, 1)
            slot_indices = _get_weekly_slot_indices(n)
            theme_list = ", ".join(slot_names[slot_indices[i]] for i in range(n))
            parts.append(f"{ch.capitalize()}: {n} posts ({theme_list})")
        week_structure_desc = ". ".join(parts)
        goals_str = ", ".join(options.campaign_goal_mix) if options.campaign_goal_mix else "awareness, engagement"

        objective_instruction: Optional[str] = None
        if getattr(options, "objective_mode", None) == "by_day" and getattr(options, "objective_by_day", None):
            by_day = options.objective_by_day
            objective_instruction = "Content objective by day of week: " + ", ".join(
                f"{d}= {o}" for d, o in sorted(by_day.items())
            ) + ". Align each post with its day's objective."
        elif getattr(options, "objective_mode", None) == "by_post" and getattr(options, "objective_by_post", None):
            n = len(options.objective_by_post)
            objective_instruction = (
                f"Content objective per post (in slot order, repeating every {n} slots): "
                + ", ".join(f"slot {i+1}= {o}" for i, o in enumerate(options.objective_by_post))
                + ". Align each post with its slot's objective."
            )

        system = _build_monthly_generation_system_prompt(
            lang_label=lang_label,
            language_code=language,
            channels_str=channels_str,
            distribution_strategy=options.distribution_strategy,
            posts_per_channel_per_week=per_channel,
            total_per_week=total_per_week,
            total_posts=total_posts,
            week_structure_desc=week_structure_desc,
            goals_str=goals_str,
            length_instruction=length_instruction,
            call_to_action_required=options.call_to_action_required,
            objective_instruction=objective_instruction,
            example_platform=options.channels[0] if options.channels else None,
        )
        user = _build_monthly_generation_user_prompt(
            campaign_name=campaign_name,
            description=description or "N/A",
            channels_str=channels_str,
        )
        url = f"{settings.AI_API_URL.rstrip('/')}/chat/completions"
        payload = {
            "model": "gpt-4" if "openai" in (settings.AI_PROVIDER or "").lower() else "gpt-4",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return AIService._generate_mock(campaign_name, description, options)
            text = choices[0].get("message", {}).get("content", "[]")
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            posts = json.loads(text)
            allowed_platforms = set(options.channels)
            objectives = _compute_objectives_for_plan(options)
            for i, p in enumerate(posts):
                validate_content_language(p.get("content", ""), language)
                plat = (p.get("platform") or "").lower()
                if plat not in allowed_platforms:
                    p["platform"] = options.channels[0]
                # Normalize optional fields for storage
                if p.get("link") is None or (isinstance(p.get("link"), str) and not p.get("link", "").strip()):
                    p["link"] = ""
                if "hashtags" not in p:
                    p["hashtags"] = []
                if "campaign_goal_tag" not in p:
                    p["campaign_goal_tag"] = options.campaign_goal_mix[0] if options.campaign_goal_mix else "engagement"
                # Preserve assigned content objective (by slot order)
                p["content_objective"] = objectives[i] if i < len(objectives) else "education"
            return posts
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            return AIService._generate_mock(campaign_name, description, options)

    @staticmethod
    def generate_campaign_plan(
        campaign_name: str,
        description: str = None,
        language: str = "es",
    ) -> Dict[str, Any]:
        """Legacy: returns a mock plan structure."""
        plan = {
            "theme": campaign_name,
            "description": description or "",
            "language": language,
            "posts_count": 5,
            "posting_schedule": "daily",
            "content_themes": [
                f"Introduction to {campaign_name}",
                f"Benefits of {campaign_name}",
                f"Success stories related to {campaign_name}",
                f"Tips and best practices for {campaign_name}",
                f"Call to action for {campaign_name}",
            ],
            "target_audience": "General audience",
            "tone": "Professional and engaging",
        }
        return plan

    @staticmethod
    def generate_posts(
        campaign_plan: Dict[str, Any],
        language: str = "es",
    ) -> List[Dict[str, Any]]:
        """Legacy: returns mock posts from plan. Platform round-robins over supported channels."""
        posts = []
        content_themes = campaign_plan.get("content_themes", [])
        posts_count = campaign_plan.get("posts_count", 5)
        channel_list = sorted(ALLOWED_CHANNELS)
        for i, theme in enumerate(content_themes[:posts_count]):
            platform = channel_list[i % len(channel_list)] if channel_list else "linkedin"
            if language == "es":
                content = (
                    f"🎯 {theme}\n\n"
                    "Este es un post de ejemplo generado para la campaña. "
                    f"Contenido relevante que se adapta al tema: {theme}.\n\n"
                    "#MarketingDigital #SocialMedia"
                )
            else:
                content = (
                    f"🎯 {theme}\n\n"
                    "This is an example post generated for the campaign. "
                    f"Relevant content that adapts to the theme: {theme}.\n\n"
                    "#DigitalMarketing #SocialMedia"
                )
            posts.append({
                "content": content,
                "platform": platform,
                "metadata": {"theme": theme, "order": i + 1},
            })
        return posts
