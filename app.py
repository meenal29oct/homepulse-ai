import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from labeler import LABELS, LABEL_DEFINITIONS, analyze_comment
from review import review_reasons
from demo_data import seed_demo_data


st.set_page_config(
    page_title="HomePulse AI",
    page_icon="🏠",
    layout="wide"
)

QUESTION = (
    "Which parts of apartment living need management's "
    "attention, and which comments need a person to read them?"
)

DB_PATH = Path("homepulse_feedback.db")


def connect():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.execute("PRAGMA busy_timeout=15000")
    return connection


def initialize_database():
    with connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                rating INTEGER,
                comment TEXT,
                topic TEXT,
                classification_error TEXT,
                needs_review INTEGER NOT NULL DEFAULT 0,
                review_reason TEXT,
                is_demo INTEGER NOT NULL DEFAULT 0
            )
        """)

        columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(feedback)"
            )
        }

        if "is_demo" not in columns:
            connection.execute(
                "ALTER TABLE feedback ADD COLUMN "
                "is_demo INTEGER NOT NULL DEFAULT 0"
            )

        seed_demo_data(connection)


def save_feedback(rating, comment, topic, error, reasons):
    with connect() as connection:
        connection.execute("""
            INSERT INTO feedback ( 
                timestamp, rating, comment, topic,
                classification_error, needs_review,
                review_reason, is_demo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            datetime.now(timezone.utc).isoformat(),
            rating,
            comment or None,
            topic,
            error,
            int(bool(reasons)),
            "; ".join(reasons),
        ))


def load_feedback():
    with connect() as connection:
        return pd.read_sql_query(
            "SELECT * FROM feedback ORDER BY id DESC",
            connection
        )


initialize_database()

st.sidebar.title("🏠 HomePulse AI")
st.sidebar.caption("Apartment Resident Feedback Analyzer")

page = st.sidebar.radio(
    "Navigation",
    ["Resident Feedback", "Manager Dashboard"]
)

st.sidebar.divider()
st.sidebar.caption(
    "Public classroom demonstration. "
    "Use fictional feedback only."
)


# =========================================
# RESIDENT PAGE
# =========================================

if page == "Resident Feedback":

    st.title("🏠 HomePulse AI")
    st.subheader("Better living starts with your feedback")

    st.write(
        "Tell us about living at HomePulse. You can leave a star "
        "rating, a written comment, or both. At least one is required."
    )

    st.markdown(
        "**How it works**\n"
        "1. Write a short comment about any part of apartment life, "
        "such as repairs, noise, safety, staff, or shared spaces.\n"
        "2. AI assigns your comment to one topic.\n"
        "3. Managers see topic trends on the **Manager Dashboard**, "
        "and comments that may need a person to read them are "
        "flagged for review."
    )

   
    st.caption(
        "Please submit fictional feedback only. "
        "Comments in any language are welcome. "
        "You may also submit a star rating without a comment."
    )

    st.warning(
        "**Public demo. Use fictional feedback only.** No names, "
        "apartment numbers, addresses, or phone numbers. Comments "
        "are sent to Groq and are visible on the public dashboard. "
        "This is not an emergency service. For fire, gas leaks, or "
        "immediate danger, call 911."
    )


    with st.form("feedback_form", clear_on_submit=False):

        rating_choice = st.selectbox(
            "Star rating",
            [
                "No rating",
                "1 ⭐",
                "2 ⭐⭐",
                "3 ⭐⭐⭐",
                "4 ⭐⭐⭐⭐",
                "5 ⭐⭐⭐⭐⭐",
            ]
        )

        comment = st.text_area(
            "Written feedback",
            placeholder=(
                "Example: The laundry room is clean, "
                "but the machines are often unavailable."
            ),
            height=140,
            max_chars=5000,
        )

        submitted = st.form_submit_button(
            "Submit feedback",
            type="primary",
            width="stretch"
        )


    if submitted:

        rating = (
            None if rating_choice == "No rating"
            else int(rating_choice[0])
        )

        comment = comment.strip()

        if rating is None and not comment:
            st.error(
                "Please provide a rating, a comment, or both."
            )

        else:
            topic = None
            error = None
            reasons = []
            classification_ok = True
            ai_needs_review = False
            ai_review_reason = ""
            api_key = ""

            if comment:
                try:
                    api_key = st.secrets.get("GROQ_API_KEY", "")
                except Exception:
                    api_key = ""

                if not api_key:
                    classification_ok = False
                else:
                     with st.spinner("Analyzing your feedback..."):
                        (
                            topic,
                            ai_needs_review,
                            ai_review_reason,
                            error
                        ) = analyze_comment(comment, api_key)

                        if (error or topic not in LABELS) and not (
                            error and "RateLimitError" in error
                        ):
                            (
                                topic,
                                ai_needs_review,
                                ai_review_reason,
                                error
                            ) = analyze_comment(comment, api_key)

                     classification_ok = (
                        error is None and topic in LABELS
                    )

                if classification_ok:
                    reasons = review_reasons(
                        comment,
                        rating,
                        topic,
                        ai_needs_review=ai_needs_review,
                        ai_review_reason=ai_review_reason
                    )

            
            if not classification_ok:
                if error and "RateLimitError" in error:
                    st.error(
                        "The AI service is temporarily busy or has "
                        "reached its usage limit. Your feedback has "
                        "not been saved. Please try again later."
                    )
                else:
                    st.error(
                        "We couldn't classify your comment. "
                        "Your feedback has not been saved."
                    )

                    if not api_key:
                        st.warning(
                            "Groq API key is missing. "
                            "Check GROQ_API_KEY in Streamlit Secrets."
                        )
                    elif error:
                        st.warning(f"Classification error: {error}")
                    else:
                        st.warning("Groq did not return a valid topic.")

            else:
                try:
                    save_feedback(
                        rating, comment, topic, None, reasons
                    )
                except sqlite3.Error:
                    st.error(
                        "The feedback could not be saved. "
                        "Please try again."
                    )
                else:
                    st.success(
                        "Thank you! Your feedback was saved and "
                        "now appears on the Manager Dashboard."
                    )

                    if comment:
                        st.write(
                            f"**Assigned topic:** {topic}"
                        )

                    if reasons:
                        st.caption(
                            "A manager will be asked to read this comment "
                            "because it matched an automatic review "
                            "check. This does not trigger an emergency "
                            "response."
                        )


    
    with st.expander("How does classification work?"):
        st.write(
            "Groq assigns one topic and suggests whether "
            "a person should review the comment. "
            "Keyword and pattern rules add further review flags."
        )

        for label, definition in LABEL_DEFINITIONS.items():
            st.write(f"**{label}:** {definition}")


# =========================================
# MANAGER DASHBOARD
# =========================================

else:

    st.title("📊 Manager Dashboard")
    st.write(f"**Business question:** {QUESTION}")
    st.caption(
        "To test: submit feedback on the Resident Feedback page "
        "(left sidebar), then return here. Counts, charts and the "
        "review list update automatically."
    )

    st.info(
        "This dashboard includes fictional, pre-labeled sample "
        "records and public visitor test submissions. "
        "Sample records are not live LLM predictions. "
        "The figures do not represent real apartment performance."
    )

    df = load_feedback()

    if df.empty:
        st.info("No feedback is available.")
        st.stop()

    demo_count = int(df["is_demo"].sum())
    visitor_count = len(df) - demo_count

    st.caption(
        f"{demo_count} fictional sample records • "
        f"{visitor_count} visitor test submissions"
    )

    # Three required KPIs
    total = len(df)
    rated = df.dropna(subset=["rating"])
    average = (
        rated["rating"].mean()
        if not rated.empty else None
    )
    review_count = int(df["needs_review"].sum())

    k1, k2, k3 = st.columns(3)


    k1.metric("Feedback received", total)
    k2.metric(
        "Average rating",
        f"{average:.2f} / 5" if average is not None else "N/A"
    )
    k3.metric("Needs manual review", review_count)

    rating_only_count = int(
        (df["rating"].notna() & df["comment"].isna()).sum()
    )

    st.caption(
        f"Of {total} feedback submissions, "
        f"{rating_only_count} contain only a star rating. "
        "Rating-only submissions contribute to the total feedback "
        "count and overall average rating, but are excluded "
        "from topic charts because they have no written comment."
    )

    st.divider()


    # Chart 1
    st.subheader("1. Which topics are mentioned most?")

    labeled = df[df["topic"].isin(LABELS)].copy()

    if labeled.empty:
        st.info("No classified comments available.")
    else:
        counts = (
            labeled["topic"]
            .value_counts()
            .reindex(LABELS, fill_value=0)
        )

        st.bar_chart(
            counts.rename("Comments"),
            horizontal=True
        )

    st.caption(
        "Topic counts include both praise and complaints. "
        "They do not measure the number of problems. "
        "Rating-only and unclassified submissions "
        "are excluded."
    )

    # Chart 2
    st.subheader("2. Which topics receive lower star ratings?")

    rated_comments = labeled.dropna(subset=["rating"])

    if rated_comments.empty:
        st.info(
            "No comments currently have both "
            "a topic and a rating."
        )
    else:
        grouped = (
            rated_comments.groupby("topic")["rating"]
            .agg(["mean", "count"])
            .reindex(LABELS)
            .dropna(subset=["mean"])
        )

        st.bar_chart(
            grouped["mean"].rename("Average stars"),
            horizontal=True
        )

        with st.expander("View average ratings and sample sizes"):
            st.dataframe(
                grouped.rename(columns={
                    "mean": "Average stars",
                    "count": "Rated comments"
                }),
                width="stretch"
            )

        eligible = grouped[grouped["count"] >= 3]

        if not eligible.empty:
            lowest = eligible["mean"].idxmin()
            mean = float(eligible.loc[lowest, "mean"])
            n = int(eligible.loc[lowest, "count"])

            st.info(
                f"**Area to examine:** {lowest} has the lowest "
                f"average rating among topics with at least "
                f"three rated comments ({mean:.2f}/5; n={n}). "
                "This is an exploratory signal, not proof "
                "of a service problem."
            )
        else:
            st.caption(
                "There are too few rated comments per topic "
                "to identify a meaningful lowest-rated area."
            )

    st.caption(
        "Ratings without comments contribute to the overall "
        "average, but cannot be assigned to a topic. "
        "Fictional sample records are included in these charts."
    )

    st.divider()

    # Full flagged comments
    st.subheader("3. Comments needing manual review")

    flagged = df[
        (df["needs_review"] == 1)
        & df["comment"].notna()
    ].copy()

    if flagged.empty:
        st.success(
            "No comments currently match the screening rules."
        )
    else:
        st.write(f"**{len(flagged)} comments flagged.**")

        available_reasons = sorted({
            reason.strip()
            for value in flagged["review_reason"].fillna("")
            for reason in value.split(";")
            if reason.strip()
        })

        reason_filter = st.selectbox(
            "Filter by review reason",
            ["All reasons"] + available_reasons
        )

        if reason_filter != "All reasons":
            flagged = flagged[
                flagged["review_reason"]
                .fillna("")
                .str.contains(reason_filter, regex=False)
            ]

        for _, item in flagged.iterrows():
            topic = (
                item["topic"]
                if pd.notna(item["topic"])
                else "Unclassified"
            )

            rating = (
                f'{int(item["rating"])} / 5'
                if pd.notna(item["rating"])
                else "No rating"
            )

            
            source = (
                "Fictional sample"
                if int(item["is_demo"]) == 1
                else "Visitor test"
            )

            with st.container(border=True):
                st.write("**Resident comment:**")
                st.text(item["comment"])

                st.write(
                    f"**Topic:** {topic} | **Rating:** {rating}"
                )

                st.warning(
                    "Needs manager review — "
                    + str(item["review_reason"])
                )

                st.caption(
                    f"{source} • "
                    + datetime.fromisoformat(
                        item["timestamp"]
                    ).strftime("%b %d, %Y at %I:%M %p UTC")
                )


    st.divider()

    with st.expander("Export classroom feedback data (CSV)"):

        export_df = df.copy()

        export_df["comment"] = export_df["comment"].apply(
            lambda s: "'" + s
            if isinstance(s, str) and s and s[0] in "=+-@"
            else s
        )

        st.download_button(
            "Download CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name="homepulse_feedback.csv",
            mime="text/csv",
            width="stretch"
        )

    with st.expander("Methodology and limitations"):
        st.write(
            "**Classification:** Each saved written comment receives "
            "exactly one of six predefined topic labels. "
            "If classification fails after a retry, the submission "
            "is not saved and the resident is asked to try again. "
            "Rating-only submissions do not require a topic label."
        )
       
        st.write(
            "**Manual review:** AI-based screening and keyword "
            "or pattern rules identify comments that may need "
            "human attention. Both approaches can make mistakes "
            "and may miss concerns or incorrectly flag comments."
        )
        
        st.write(
            "**Interpretation:** High topic volume does not "
            "necessarily mean poor service. Average ratings "
            "are sensitive to small samples and selection bias."
        )
        st.write(
            "**Data:** Fictional records are pre-labeled. "
            "Visitor submissions are for demonstration only."
        )
        st.write(
            "**Persistence:** SQLite files on Streamlit "
            "Community Cloud are not durable storage. "
            "Visitor submissions may disappear after a restart."
        )
        st.write(
            "**Privacy:** This dashboard and CSV are public. "
            "Only fictional, non-sensitive feedback should "
            "be entered. Written comments are sent to Groq."
        )
        st.write(
            "**Emergencies:** The app is not monitored "
            "and must not be used to report emergencies."
        )
