# hsae_legal.py  –  HSAE Legal Enhancement Module
# Updated: 2026-02-26  |  Author: Seifeldin M. G. Alkhedir
# Covers:
#   1. Auto-Protest Report Generator (Equity < 40% → PDF-ready HTML)
#   2. ICJ Precedents Database (Gabcikovo, Pulp Mills, Kishenganga …)
#   3. Bilingual Reports Arabic / English
#   4. UN 1997 Article Auto-Mapper

from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# 1. ICJ PRECEDENTS DATABASE
# ══════════════════════════════════════════════════════════════════════════════

ICJ_CASES: list[dict] = [
    {
        "id": "ICJ-1997-HNG-SVK",
        "title": "Gabcikovo-Nagymaros Project (Hungary v. Slovakia)",
        "title_en": "Gabcikovo-Nagymaros Project (Hungary v. Slovakia)",
        "year": 1997,
        "river": "Danube",
        "articles_triggered": ["Art.5","Art.7","Art.20"],
        "equity_threshold": 50.0,
        "holding_en": (
            "Both states have obligations for equitable use. "
            "Unilateral diversion without notification breaches "
            "customary international water law."
        ),
        "holding_ar": (
            "لكلا الدولتين التزامات بالاستخدام المنصف. "
            "يُعدّ تحويل مجرى النهر بشكل أحادي دون إخطار "
            "انتهاكاً للقانون الدولي العرفي للمياه."
        ),
        "relevance_kw": ["diversion","unilateral","notification","equitable"],
        "url": "https://www.icj-cij.org/case/92",
    },
    {
        "id": "ICJ-2010-ARG-URY",
        "title": "Pulp Mills on the River Uruguay (Argentina v. Uruguay)",
        "title_en": "Pulp Mills on the River Uruguay (Argentina v. Uruguay)",
        "year": 2010,
        "river": "Uruguay",
        "articles_triggered": ["Art.9","Art.20"],
        "equity_threshold": 0.0,
        "holding_en": (
            "States must notify co-riparians before constructing "
            "works likely to affect shared watercourses. "
            "Environmental impact assessment is obligatory."
        ),
        "holding_ar": (
            "يجب على الدول إخطار الدول المشاطئة قبل إنشاء أعمال "
            "قد تؤثر على المجاري المائية المشتركة. "
            "تقييم الأثر البيئي إلزامي."
        ),
        "relevance_kw": ["notification","EIA","environmental","construction"],
        "url": "https://www.icj-cij.org/case/135",
    },
    {
        "id": "PCA-2013-IND-PAK",
        "title": "Kishenganga Arbitration (India v. Pakistan)",
        "title_en": "Kishenganga Arbitration (India v. Pakistan)",
        "year": 2013,
        "river": "Indus / Kishenganga",
        "articles_triggered": ["Art.5","Art.7"],
        "equity_threshold": 45.0,
        "holding_en": (
            "Minimum environmental flow obligations must be maintained. "
            "Hydropower projects on shared rivers must preserve "
            "downstream ecological integrity."
        ),
        "holding_ar": (
            "يجب الحفاظ على الحد الأدنى من التدفق البيئي. "
            "مشاريع الطاقة الكهرومائية على الأنهار المشتركة يجب "
            "أن تحافظ على سلامة النظام البيئي للمصب."
        ),
        "relevance_kw": ["minimum flow","hydropower","downstream","ecology"],
        "url": "https://pca-cpa.org/en/cases/59/",
    },
    {
        "id": "ICJ-2018-CRI-NIC",
        "title": "Certain Activities (Costa Rica v. Nicaragua)",
        "title_en": "Certain Activities (Costa Rica v. Nicaragua)",
        "year": 2018,
        "river": "San Juan",
        "articles_triggered": ["Art.7","Art.20"],
        "equity_threshold": 0.0,
        "holding_en": (
            "Environmental damage to shared watercourses gives rise "
            "to reparation obligations. "
            "Satellite imagery accepted as valid evidence."
        ),
        "holding_ar": (
            "يُولِّد الضرر البيئي للمجاري المائية المشتركة التزامات بالتعويض. "
            "قُبلت صور الأقمار الصناعية كدليل قانوني صالح."
        ),
        "relevance_kw": ["satellite","evidence","reparation","environment"],
        "url": "https://www.icj-cij.org/case/150",
    },
    {
        "id": "ITLOS-2011-BGD-MMR",
        "title": "Bay of Bengal Maritime Delimitation (Bangladesh v. Myanmar)",
        "title_en": "Bay of Bengal Maritime Delimitation (Bangladesh v. Myanmar)",
        "year": 2012,
        "river": "N/A (Maritime)",
        "articles_triggered": ["Art.9"],
        "equity_threshold": 0.0,
        "holding_en": (
            "Data transparency and sharing obligations apply "
            "to all shared water resources, including maritime zones."
        ),
        "holding_ar": (
            "تسري التزامات الشفافية وتبادل البيانات على جميع الموارد "
            "المائية المشتركة بما فيها المناطق البحرية."
        ),
        "relevance_kw": ["transparency","data","sharing","maritime"],
        "url": "https://www.itlos.org/cases/list-of-cases/case-no-16/",
    },
    {
        "id": "UNSC-2020-ETH-SDN-EGY",
        "title": "GERD Negotiation Framework (Ethiopia–Sudan–Egypt)",
        "title_en": "GERD Negotiation Framework (Ethiopia–Sudan–Egypt)",
        "year": 2020,
        "river": "Blue Nile",
        "articles_triggered": ["Art.5","Art.7","Art.9","Art.12"],
        "equity_threshold": 40.0,
        "holding_en": (
            "Ongoing dispute under UNSC Resolution 2519 (2020). "
            "No binding agreement reached; equity and data transparency "
            "remain central to tripartite negotiations."
        ),
        "holding_ar": (
            "نزاع مستمر بموجب قرار مجلس الأمن 2519 (2020). "
            "لم يُتوصَّل إلى اتفاق ملزم؛ تبقى العدالة وشفافية البيانات "
            "محور المفاوضات الثلاثية."
        ),
        "relevance_kw": ["gerd","nile","ethiopia","egypt","sudan","equity"],
        "url": "https://www.un.org/securitycouncil/content/s2020-657",
    },
]


def find_relevant_cases(
    equity_pct:    float,
    forensic_score:float,
    basin_tags:    list[str] | None = None,
) -> list[dict]:
    """Return ICJ cases relevant to current basin metrics."""
    relevant = []
    tags = [t.lower() for t in (basin_tags or [])]

    for case in ICJ_CASES:
        score = 0
        if equity_pct < case["equity_threshold"]:
            score += 3
        if forensic_score > 50 and any(
            k in ["diversion","unilateral","hydropower"]
            for k in case["relevance_kw"]
        ):
            score += 2
        if tags and any(k in tags for k in case["relevance_kw"]):
            score += 2
        if score > 0:
            relevant.append({**case, "_relevance": score})

    return sorted(relevant, key=lambda x: -x["_relevance"])


# ══════════════════════════════════════════════════════════════════════════════
# 2. UN 1997 ARTICLE AUTO-MAPPER
# ══════════════════════════════════════════════════════════════════════════════

UN1997_ARTICLES: dict[str, dict] = {
    "Art.5": {
        "title_en": "Equitable and Reasonable Utilization",
        "title_ar": "الاستخدام المنصف والمعقول",
        "trigger":  lambda eq, fs, td: eq < 60,
        "text_en":  "Watercourse States shall utilize shared watercourses "
                    "in an equitable and reasonable manner.",
        "text_ar":  "تستخدم دول المجرى المائي المجاري المشتركة "
                    "بصورة منصفة ومعقولة.",
        "severity": lambda eq, fs, td: "CRITICAL" if eq < 30 else (
            "WARNING" if eq < 50 else "CAUTION"),
    },
    "Art.7": {
        "title_en": "Obligation Not to Cause Significant Harm",
        "title_ar": "الالتزام بعدم إحداث ضرر ذي شأن",
        "trigger":  lambda eq, fs, td: eq < 50 or fs > 60,
        "text_en":  "States shall take all appropriate measures "
                    "to prevent causing significant harm.",
        "text_ar":  "تتخذ الدول جميع التدابير المناسبة "
                    "لمنع إلحاق ضرر ذي شأن.",
        "severity": lambda eq, fs, td: "CRITICAL" if fs > 70 else "WARNING",
    },
    "Art.9": {
        "title_en": "Regular Exchange of Data and Information",
        "title_ar": "التبادل المنتظم للبيانات والمعلومات",
        "trigger":  lambda eq, fs, td: td > 15,
        "text_en":  "Watercourse States shall on a regular basis "
                    "exchange readily available data and information.",
        "text_ar":  "تتبادل دول المجرى المائي بانتظام البيانات "
                    "والمعلومات المتاحة بسهولة.",
        "severity": lambda eq, fs, td: "CRITICAL" if td > 30 else "WARNING",
    },
    "Art.20": {
        "title_en": "Protection and Preservation of Ecosystems",
        "title_ar": "حماية النظم البيئية والمحافظة عليها",
        "trigger":  lambda eq, fs, td: eq < 40,
        "text_en":  "States shall protect and preserve the ecosystems "
                    "of international watercourses.",
        "text_ar":  "تحمي الدول النظم البيئية للمجاري المائية الدولية وتصونها.",
        "severity": lambda eq, fs, td: "WARNING",
    },
    "Art.12": {
        "title_en": "Notification Concerning Planned Measures",
        "title_ar": "الإخطار بالتدابير المخطط لها",
        "trigger":  lambda eq, fs, td: fs > 50,
        "text_en":  "States shall provide timely notification of "
                    "planned measures with significant adverse effects.",
        "text_ar":  "تُبلِّغ الدول في الوقت المناسب بالتدابير المخطط لها "
                    "ذات الآثار الضارة الكبيرة.",
        "severity": lambda eq, fs, td: "WARNING",
    },
    "Art.6": {
        "title_en": "Factors Relevant to Equitable Utilization",
        "title_ar": "العوامل ذات الصلة بالاستخدام المنصف",
        "trigger":  lambda eq, fs, td: eq < 55,
        "text_en":  "Utilization shall consider geographic, hydrologic, "
                    "climatic, ecological and social factors including "
                    "population dependence and effects of use on other states.",
        "text_ar":  "يراعي الاستخدام العوامل الجغرافية والهيدرولوجية "
                    "والمناخية والبيئية والاجتماعية بما فيها الاعتماد السكاني.",
        "severity": lambda eq, fs, td: "WARNING" if eq < 50 else "CAUTION",
    },
    "Art.8": {
        "title_en": "General Obligation to Cooperate",
        "title_ar": "الالتزام العام بالتعاون",
        "trigger":  lambda eq, fs, td: td > 20 or fs > 40,
        "text_en":  "Watercourse States shall cooperate on the basis of "
                    "sovereign equality, territorial integrity and mutual benefit.",
        "text_ar":  "تتعاون دول المجرى المائي على أساس المساواة في السيادة "
                    "والسلامة الإقليمية والمنفعة المتبادلة.",
        "severity": lambda eq, fs, td: "WARNING",
    },
    "Art.10": {
        "title_en": "Relationship Between Different Kinds of Uses",
        "title_ar": "العلاقة بين أنواع الاستخدامات المختلفة",
        "trigger":  lambda eq, fs, td: eq < 50,
        "text_en":  "No use of an international watercourse enjoys inherent "
                    "priority over other uses. Special regard shall be given "
                    "to vital human needs.",
        "text_ar":  "لا يتمتع أي استخدام للمجرى المائي الدولي بأولوية "
                    "متأصلة على الاستخدامات الأخرى. تُولى عناية خاصة للاحتياجات البشرية الحيوية.",
        "severity": lambda eq, fs, td: "CRITICAL" if eq < 30 else "WARNING",
    },
    "Art.11": {
        "title_en": "Information Concerning Planned Measures",
        "title_ar": "المعلومات المتعلقة بالتدابير المخطط لها",
        "trigger":  lambda eq, fs, td: fs > 40,
        "text_en":  "Before implementing measures with significant adverse "
                    "effects, the State shall provide relevant information "
                    "to other watercourse States.",
        "text_ar":  "قبل تنفيذ التدابير ذات الآثار الضارة الكبيرة تزود الدولة "
                    "الدول الأخرى بالمعلومات ذات الصلة.",
        "severity": lambda eq, fs, td: "WARNING",
    },
    "Art.13": {
        "title_en": "Time Frame for Reply to Notification",
        "title_ar": "الإطار الزمني للرد على الإخطار",
        "trigger":  lambda eq, fs, td: fs > 50,
        "text_en":  "Notified States shall reply within six months unless "
                    "the nature of the planned measures requires a longer period.",
        "text_ar":  "ترد الدول المُخطَرة خلال ستة أشهر ما لم تستلزم طبيعة "
                    "التدابير المخطط لها فترة أطول.",
        "severity": lambda eq, fs, td: "CAUTION",
    },
    "Art.14": {
        "title_en": "Obligations of the Notifying State",
        "title_ar": "التزامات الدولة المُخطِرة",
        "trigger":  lambda eq, fs, td: fs > 55,
        "text_en":  "While awaiting reply, the notifying State shall not "
                    "implement planned measures without consent of notified States.",
        "text_ar":  "في انتظار الرد، لا تنفذ الدولة المُخطِرة التدابير المخطط لها "
                    "دون موافقة الدول المُخطَرة.",
        "severity": lambda eq, fs, td: "WARNING",
    },
    "Art.15": {
        "title_en": "Reply to Notification",
        "title_ar": "الرد على الإخطار",
        "trigger":  lambda eq, fs, td: fs > 50,
        "text_en":  "The notified State shall communicate its findings "
                    "and conclusions within the reply period, with reasons.",
        "text_ar":  "تبلغ الدولة المُخطَرة بنتائجها واستنتاجاتها خلال فترة الرد مع الأسباب.",
        "severity": lambda eq, fs, td: "CAUTION",
    },
    "Art.16": {
        "title_en": "Absence of Reply to Notification",
        "title_ar": "غياب الرد على الإخطار",
        "trigger":  lambda eq, fs, td: fs > 55,
        "text_en":  "If no reply within the period, the notifying State may "
                    "proceed with implementation in accordance with the notification.",
        "text_ar":  "إذا لم يرد رد خلال المدة، يجوز للدولة المُخطِرة المضي في التنفيذ.",
        "severity": lambda eq, fs, td: "CAUTION",
    },
    "Art.17": {
        "title_en": "Consultations and Negotiations Concerning Planned Measures",
        "title_ar": "المشاورات والمفاوضات بشأن التدابير المخطط لها",
        "trigger":  lambda eq, fs, td: fs > 45 or eq < 45,
        "text_en":  "If objections are raised, States shall enter into "
                    "consultations and negotiations in a spirit of good faith.",
        "text_ar":  "إذا أُثيرت اعتراضات تدخل الدول في مشاورات ومفاوضات "
                    "بروح من حسن النية.",
        "severity": lambda eq, fs, td: "WARNING" if eq < 40 else "CAUTION",
    },
    "Art.18": {
        "title_en": "Procedures in Absence of Notification",
        "title_ar": "الإجراءات في غياب الإخطار",
        "trigger":  lambda eq, fs, td: fs > 60 and td > 25,
        "text_en":  "If a State has reasonable grounds to believe another "
                    "is planning harmful measures without notification, it "
                    "may request information and consultations.",
        "text_ar":  "إذا كان لدى دولة أسباب معقولة للاعتقاد بأن دولة أخرى "
                    "تخطط لتدابير ضارة دون إخطار، يجوز لها طلب المعلومات.",
        "severity": lambda eq, fs, td: "CRITICAL" if fs > 70 else "WARNING",
    },
    "Art.19": {
        "title_en": "Urgent Implementation of Planned Measures",
        "title_ar": "التنفيذ العاجل للتدابير المخطط لها",
        "trigger":  lambda eq, fs, td: fs > 65,
        "text_en":  "Where urgent implementation is required for public "
                    "health or safety, the State may proceed with immediate "
                    "notification and offer of consultations.",
        "text_ar":  "عند الحاجة إلى تنفيذ عاجل لأسباب تتعلق بالصحة أو السلامة العامة "
                    "يجوز للدولة المضي مع الإخطار الفوري وعرض المشاورات.",
        "severity": lambda eq, fs, td: "WARNING",
    },
    "Art.21": {
        "title_en": "Prevention, Reduction and Control of Pollution",
        "title_ar": "منع التلوث وخفضه والسيطرة عليه",
        "trigger":  lambda eq, fs, td: td > 10,
        "text_en":  "States shall prevent, reduce and control pollution "
                    "that may cause significant harm to other States or "
                    "to the environment, including human health.",
        "text_ar":  "تمنع الدول التلوث الذي قد يُلحق ضرراً ذا شأن بدول أخرى "
                    "أو بالبيئة بما فيها صحة الإنسان وتخفضه وتسيطر عليه.",
        "severity": lambda eq, fs, td: "CRITICAL" if td > 30 else "WARNING",
    },
}

SEVERITY_COLOR = {
    "CRITICAL": "#ef4444",
    "WARNING":  "#f59e0b",
    "CAUTION":  "#3b82f6",
}


def map_articles(equity_pct: float, forensic_score: float,
                 td_index: float) -> list[dict]:
    """Return triggered articles with severity."""
    triggered = []
    for art, cfg in UN1997_ARTICLES.items():
        if cfg["trigger"](equity_pct, forensic_score, td_index):
            triggered.append({
                "article":    art,
                "title_en":   cfg["title_en"],
                "title_ar":   cfg["title_ar"],
                "text_en":    cfg["text_en"],
                "text_ar":    cfg["text_ar"],
                "severity":   cfg["severity"](equity_pct, forensic_score,
                                              td_index),
                "color":      SEVERITY_COLOR.get(
                    cfg["severity"](equity_pct, forensic_score, td_index),
                    "#6b7280"),
            })
    return triggered


# ══════════════════════════════════════════════════════════════════════════════
# 3. BILINGUAL REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

_PROTEST_TEMPLATE_EN = """
<h2>FORMAL PROTEST NOTE</h2>
<h3>Re: Hydrological Rights Violation — {basin_id}</h3>
<p><b>Date:</b> {date}</p>
<p><b>Submitting Party:</b> {submitting_party}</p>
<p><b>Respondent:</b> {respondent}</p>
<hr>
<h3>Technical Evidence</h3>
<ul>
  <li><b>Equity Index (30-day avg):</b> {equity:.1f}% (Threshold: 40%)</li>
  <li><b>Forensic Anomaly Score:</b> {forensic:.1f}%</li>
  <li><b>Transparency Deficit:</b> {td:.1f}%</li>
  <li><b>Mass-Balance Closure Error:</b> {closure:.4f}%</li>
  <li><b>Analysis Period:</b> {period}</li>
</ul>
<h3>Triggered UN 1997 Articles</h3>
{articles_html}
<h3>Relevant ICJ Precedents</h3>
{cases_html}
<h3>Demands</h3>
<ol>
  <li>Immediate restoration of equitable flow allocation.</li>
  <li>Full disclosure of operational data per Art. 9.</li>
  <li>Independent fact-finding mission per Annex Art. 6.</li>
  <li>Provisional measures pending negotiation per Annex Art. 7.</li>
</ol>
<h3>Legal Reservation</h3>
<p>This note is submitted without prejudice to all rights and remedies
available under international law, including referral to arbitration
or the International Court of Justice.</p>
<hr>
<p><i>Generated by HydroSovereign AI Engine (HSAE) —
Technical evidence tool supporting diplomatic negotiations.</i></p>
"""

_PROTEST_TEMPLATE_AR = """
<div dir="rtl" lang="ar">
<h2>مذكرة احتجاج رسمية</h2>
<h3>بشأن: انتهاك الحقوق الهيدرولوجية — {basin_id}</h3>
<p><b>التاريخ:</b> {date}</p>
<p><b>الطرف المُقدِّم:</b> {submitting_party}</p>
<p><b>المُدَّعى عليه:</b> {respondent}</p>
<hr>
<h3>الأدلة التقنية</h3>
<ul>
  <li><b>مؤشر الإنصاف (متوسط 30 يوماً):</b> {equity:.1f}٪ (العتبة: 40٪)</li>
  <li><b>درجة الشذوذ الجنائي:</b> {forensic:.1f}٪</li>
  <li><b>عجز الشفافية:</b> {td:.1f}٪</li>
  <li><b>خطأ إغلاق الميزان المائي:</b> {closure:.4f}٪</li>
  <li><b>فترة التحليل:</b> {period}</li>
</ul>
<h3>مواد اتفاقية الأمم المتحدة 1997 المنتهَكة</h3>
{articles_html}
<h3>سوابق محكمة العدل الدولية ذات الصلة</h3>
{cases_html}
<h3>المطالب</h3>
<ol>
  <li>الاستعادة الفورية للتوزيع المنصف للتدفقات.</li>
  <li>الكشف الكامل عن البيانات التشغيلية وفق المادة 9.</li>
  <li>بعثة لتقصي الحقائق بصورة مستقلة وفق المرفق المادة 6.</li>
  <li>تدابير مؤقتة ريثما تُستكمل المفاوضات وفق المرفق المادة 7.</li>
</ol>
<h3>تحفظ قانوني</h3>
<p>تُقدَّم هذه المذكرة دون الإخلال بجميع الحقوق وسبل الانتصاف المتاحة
بموجب القانون الدولي، بما فيها الإحالة إلى التحكيم أو محكمة العدل الدولية.</p>
<hr>
<p><i>صادر عن محرك HydroSovereign AI Engine (HSAE) —
أداة تقنية لدعم المفاوضات الدبلوماسية.</i></p>
</div>
"""

_COMPLIANCE_TEMPLATE_EN = """
<h2>HYDROLOGICAL COMPLIANCE REPORT</h2>
<h3>Basin: {basin_id} | Period: {period}</h3>
<p><b>Date Generated:</b> {date}</p>
<hr>
<h3>Compliance Summary</h3>
<table border="1" cellpadding="6" style="border-collapse:collapse;">
  <tr><th>Indicator</th><th>Value</th><th>Status</th></tr>
  <tr><td>Equity Index</td><td>{equity:.1f}%</td>
      <td style="color:{equity_color}">{equity_status}</td></tr>
  <tr><td>Transparency</td><td>{transparency:.1f}%</td>
      <td style="color:{transp_color}">{transp_status}</td></tr>
  <tr><td>Forensic Score</td><td>{forensic:.1f}%</td>
      <td style="color:{forensic_color}">{forensic_status}</td></tr>
  <tr><td>MB Closure Error</td><td>{closure:.4f}%</td>
      <td style="color:{closure_color}">{closure_status}</td></tr>
</table>
<hr>
<p><i>HSAE — HydroSovereign AI Engine</i></p>
"""


def generate_protest_report(
    basin_id:         str,
    equity_pct:       float,
    forensic_score:   float,
    td_index:         float,
    closure_error:    float,
    period:           str,
    submitting_party: str = "Downstream Riparian State",
    respondent:       str = "Upstream Riparian State",
    language:         str = "en",
    basin_tags:       list[str] | None = None,
) -> str:
    """Generate a bilingual protest note or compliance report HTML."""
    date_str  = datetime.utcnow().strftime("%d %B %Y")
    articles  = map_articles(equity_pct, forensic_score, td_index)
    cases     = find_relevant_cases(equity_pct, forensic_score, basin_tags)

    art_key    = "title_ar" if language == "ar" else "title_en"
    case_key   = "holding_ar" if language == "ar" else "holding_en"

    articles_html = "".join(
        f'<p><span style="color:{a["color"]};font-weight:700;">'
        f'{a["article"]} — {a[art_key]}</span><br>'
        f'<small>{a["text_ar" if language=="ar" else "text_en"]}</small></p>'
        for a in articles
    ) or "<p>No articles triggered.</p>"

    cases_html = "".join(
        f'<p><b>{c.get("title_en","—")}</b> ({c["year"]})<br>'
        f'<i>{c[case_key]}</i></p>'
        for c in cases[:3]
    ) or "<p>No directly relevant precedents.</p>"

    tmpl = _PROTEST_TEMPLATE_AR if language == "ar" else _PROTEST_TEMPLATE_EN
    return tmpl.format(
        basin_id=basin_id, date=date_str, period=period,
        submitting_party=submitting_party, respondent=respondent,
        equity=equity_pct, forensic=forensic_score,
        td=td_index, closure=closure_error,
        articles_html=articles_html, cases_html=cases_html,
    )


def generate_compliance_report(
    basin_id:     str,
    equity_pct:   float,
    forensic_score:float,
    td_index:     float,
    closure_error: float,
    period:       str,
    transparency: float = 97.0,
) -> str:
    """Generate compliance report HTML (English only)."""
    def _color(val, good, warn):
        return "green" if val >= good else ("orange" if val >= warn else "red")
    def _status(val, good, warn):
        return "✅ COMPLIANT" if val >= good else (
            "⚠ WARNING" if val >= warn else "🚨 VIOLATION")

    closure_color  = "green" if closure_error < 1 else "red"
    closure_status = "✅ PASS" if closure_error < 1 else "⚠ FAIL"
    return _COMPLIANCE_TEMPLATE_EN.format(
        basin_id=basin_id, period=period,
        date=datetime.utcnow().strftime("%d %B %Y"),
        equity=equity_pct,
        equity_color=_color(equity_pct, 60, 40),
        equity_status=_status(equity_pct, 60, 40),
        transparency=transparency,
        transp_color=_color(transparency, 90, 75),
        transp_status=_status(transparency, 90, 75),
        forensic=forensic_score,
        forensic_color=_color(100-forensic_score, 60, 40),
        forensic_status=_status(100-forensic_score, 60, 40),
        closure=closure_error,
        closure_color=closure_color,
        closure_status=closure_status,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

def render_legal_page(basin: dict) -> None:
    """Full legal enhancement UI."""

    equity_pct     = st.session_state.get("equity_index_mean",   55.0)
    forensic_score = st.session_state.get("forensic_score",      30.0)
    td_index       = st.session_state.get("td_index",             5.0)
    closure_error  = st.session_state.get("closure_error",        0.05)
    transparency   = 100.0 - td_index
    basin_id       = basin.get("id", "Unknown")
    basin_tags     = basin.get("tags", [])
    t_start        = st.session_state.get("time_start","2022-01-01")
    t_end          = st.session_state.get("time_end",  "2023-01-01")
    period         = f"{t_start} → {t_end}"

    st.markdown("""
<style>
.law-card{background:linear-gradient(135deg,#020617,#0f172a);
  border:2px solid #3b82f6;border-radius:16px;padding:1.2rem 1.6rem;
  margin-bottom:1rem;box-shadow:0 8px 32px rgba(59,130,246,.18);}
.law-card h3{color:#60a5fa;}
.icj-card{background:#0a0f1e;border-left:4px solid #8b5cf6;
  padding:.8rem 1.2rem;border-radius:10px;margin:.5rem 0;}
.art-tag{display:inline-block;border-radius:999px;padding:.1rem .6rem;
  font-size:.75rem;font-weight:700;margin:.1rem;}
</style>""", unsafe_allow_html=True)

    st.markdown(f"""
<div class="law-card">
  <h3>⚖️ Legal Enhancement Module — {basin_id}</h3>
  <p style="color:#94a3b8;font-size:.85rem;">
    Auto-Protest Generator &bull; ICJ Precedents &bull; Bilingual Reports &bull;
    UN 1997 Auto-Mapper
  </p>
</div>""", unsafe_allow_html=True)

    l1, l2, l3, l4 = st.tabs([
        "📋 UN 1997 Monitor",
        "🏛 ICJ Precedents",
        "📄 Auto-Protest",
        "✅ Compliance Report",
    ])

    # ── Tab L1: UN 1997 Monitor ───────────────────────────────────────────
    with l1:
        st.subheader("UN 1997 Watercourses Convention — Live Monitor")

        col_eq, col_fs, col_td = st.columns(3)
        with col_eq:
            equity_pct = st.number_input(
                "Equity Index %", 0.0, 150.0, equity_pct, 0.5,
                key="legal_equity_input",
            )
        with col_fs:
            forensic_score = st.number_input(
                "Forensic Score %", 0.0, 100.0, forensic_score, 0.5,
                key="legal_forensic_input",
            )
        with col_td:
            td_index = st.number_input(
                "Transparency Deficit %", 0.0, 100.0, td_index, 0.5,
                key="legal_td_input",
            )

        articles = map_articles(equity_pct, forensic_score, td_index)

        if not articles:
            st.success("✅ All UN 1997 indicators within compliant range.")
        else:
            for a in articles:
                st.markdown(
                    f'<div style="border-left:5px solid {a["color"]}; '
                    f'padding:.7rem 1.2rem;border-radius:8px;'
                    f'background:#0d1117;margin:.5rem 0;">'
                    f'<span class="art-tag" style="background:{a["color"]}22;'
                    f'color:{a["color"]};border:1px solid {a["color"]};">'
                    f'{a["severity"]}</span>&nbsp;&nbsp;'
                    f'<b style="color:{a["color"]};">{a["article"]}</b>&nbsp;—&nbsp;'
                    f'<b>{a.get("title_en","—")}</b><br>'
                    f'<small style="color:#94a3b8;">{a["title_ar"]}</small><br>'
                    f'<small style="color:#cbd5e1;">{a["text_en"]}</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Tab L2: ICJ Precedents ────────────────────────────────────────────
    with l2:
        st.subheader("ICJ / PCA / ITLOS Precedents Database")
        search_q = st.text_input("🔍 Search cases", "",
                                  placeholder="nile · equity · satellite …",
                                  key="icj_search")

        display_cases = ICJ_CASES
        if search_q:
            q_low = search_q.lower()
            display_cases = [
                c for c in ICJ_CASES
                if q_low in c.get("title_en","—").lower()
                or q_low in c["river"].lower()
                or any(q_low in kw for kw in c["relevance_kw"])
                or q_low in c["holding_en"].lower()
            ]

        for c in display_cases:
            art_badges = "".join(
                f'<span class="art-tag" style="background:#1e3a5f;'
                f'color:#93c5fd;border:1px solid #3b82f6;">{a}</span>'
                for a in c["articles_triggered"]
            )
            st.markdown(f"""
<div class="icj-card">
  <b style="color:#c4b5fd;">{c.get("title_en","—")}</b>&nbsp;
  <small style="color:#6b7280;">({c["year"]} | {c["river"]})</small>
  <br>{art_badges}
  <br><small style="color:#94a3b8;">{c["holding_en"]}</small>
  <br><small style="color:#64748b;font-style:italic;">{c["holding_ar"]}</small>
  <br><a href="{c['url']}" target="_blank"
     style="color:#60a5fa;font-size:.75rem;">🔗 Full Case</a>
</div>""", unsafe_allow_html=True)

        rel_cases = find_relevant_cases(equity_pct, forensic_score, basin_tags)
        if rel_cases:
            st.markdown("---")
            st.markdown(
                f"### 🎯 {len(rel_cases)} Relevant Precedent(s) — "
                f"Basin: {basin_id}"
            )
            for c in rel_cases:
                st.info(
                    f"**{c['title_en']} ({c['year']})** — "
                    f"Relevance Score: {c['_relevance']}\n\n"
                    f"*{c['holding_en']}*"
                )

    # ── Tab L3: Auto-Protest ──────────────────────────────────────────────
    with l3:
        st.subheader("Auto-Protest Report Generator")

        if equity_pct >= 40:
            st.info(
                f"Equity Index = {equity_pct:.1f}% — currently above 40% threshold. "
                "Protest mode triggers automatically when Equity < 40%."
            )
        else:
            st.error(
                f"🚨 Equity Index = {equity_pct:.1f}% — BELOW 40% THRESHOLD. "
                "Protest report auto-generated."
            )

        pa, pb, pc = st.columns(3)
        with pa:
            submitter = st.text_input("Submitting Party",
                                       "Downstream Riparian State",
                                       key="submit_party")
        with pb:
            respondent = st.text_input("Respondent",
                                        "Upstream Riparian State",
                                        key="respondent")
        with pc:
            lang = st.radio("Language", ["English","Arabic"],
                            horizontal=True, key="report_lang")

        lang_code = "ar" if lang == "Arabic" else "en"

        if st.button("📄 Generate Protest Report", type="primary",
                     key="gen_protest_btn"):
            html_report = generate_protest_report(
                basin_id=basin_id,
                equity_pct=equity_pct,
                forensic_score=forensic_score,
                td_index=td_index,
                closure_error=closure_error,
                period=period,
                submitting_party=submitter,
                respondent=respondent,
                language=lang_code,
                basin_tags=basin_tags,
            )
            st.session_state["protest_html"] = html_report

        if st.session_state.get("protest_html"):
            st.components.v1.html(
                f"""<html><head>
<style>body{{font-family:Arial;padding:1rem;color:#1e293b;}}
table{{width:100%;border-collapse:collapse;}}
th,td{{padding:6px;border:1px solid #cbd5e1;}}
</style></head><body>
{st.session_state["protest_html"]}
</body></html>""",
                height=600, scrolling=True,
            )
            st.download_button(
                f"⬇ Download Protest Report ({'AR' if lang_code=='ar' else 'EN'})",
                st.session_state["protest_html"].encode("utf-8"),
                f"HSAE_Protest_{basin_id}_{lang_code.upper()}.html",
                "text/html",
                key="dl_protest",
            )
            st.info("Open in browser → Ctrl+P → Save as PDF")

    # ── Tab L4: Compliance ────────────────────────────────────────────────
    with l4:
        st.subheader("Compliance Report Generator")
        if st.button("✅ Generate Compliance Report",
                     type="primary", key="gen_compliance_btn"):
            html_c = generate_compliance_report(
                basin_id=basin_id,
                equity_pct=equity_pct,
                forensic_score=forensic_score,
                td_index=td_index,
                closure_error=closure_error,
                period=period,
                transparency=transparency,
            )
            st.session_state["compliance_html"] = html_c

        if st.session_state.get("compliance_html"):
            st.components.v1.html(
                f"""<html><head>
<style>body{{font-family:Arial;padding:1rem;}}
table{{width:100%;border-collapse:collapse;}}
th,td{{padding:8px;border:1px solid #e2e8f0;}}
</style></head><body>
{st.session_state["compliance_html"]}
</body></html>""",
                height=500, scrolling=True,
            )
            st.download_button(
                "⬇ Download Compliance Report",
                st.session_state["compliance_html"].encode("utf-8"),
                f"HSAE_Compliance_{basin_id}.html",
                "text/html",
                key="dl_compliance",
            )
