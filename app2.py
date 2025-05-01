import hmac
import streamlit as st
import tweepy
import random
from langchain.chat_models import ChatOpenAI
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from GoogleNews import GoogleNews
from newspaper import Article
import google.generativeai as genai

# Auth
app_password = st.secrets['TWITTER_NEWS_APP_PASSWORD']
api_key = st.secrets['TWITTER_API_KEY']
api_secret_key = st.secrets['TWITTER_API_KEY_SECRET']
access_token = st.secrets['TWITTER_APP_ACCESS_TOKEN']
access_token_secret = st.secrets['TWITTER_APP_ACCESS_TOKEN_SECRET']
genai_key = st.secrets['GEMINI_KEY']

# Config
genai.configure(api_key=genai_key)

# Client auth
client = tweepy.Client(
    consumer_key=api_key,
    consumer_secret=api_secret_key,
    access_token=access_token,
    access_token_secret=access_token_secret
)

# Helper functions
def remove_after_ampersand(s):
    return s.split('&', 1)[0]

def check_password():
    """Returns `True` if the user has entered the correct password."""
    def password_entered():
        env_password = app_password
        if env_password is None:
            st.error("Environment variable 'TWITTER_NEWS_APP_PASSWORD' not set.")
            return
        if hmac.compare_digest(st.session_state.get("password", ""), env_password):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct"):
        return True

    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state.password_correct:
        st.error("😕 Password incorrect")
    return False

if not check_password():
    st.stop()

# Streamlit app
st.title("Comprehensive Content Bot with Tweet Functionality")

# Input fields
topic = st.text_input("Enter the topic for news search")
persona = st.text_input("Enter the persona")
bot_title = st.text_input("Enter bot title")

# LangChain setup
llm = ChatOpenAI(
    temperature=0.7,
    model="gpt-3.5-turbo",
    verbose=True
)

# Persona Tool
def persona_research_tool(query: str) -> str:
    """Fetch meaningful persona research using the LLM."""
    prompt = (
        f"Provide detailed information about the persona named '{query}'. Include their background, "
        "characteristics, and any relevant context or insights."
    )
    try:
        result = llm.predict(prompt)
        return result.strip() if result else "No meaningful information found for this persona."
    except Exception as e:
        return f"Error retrieving persona information: {e}"

# Topic Tool
def topic_research_tool(query: str) -> str:
    """Fetch topic research information using the LLM."""
    prompt = f"Research and provide insights about the topic '{query}'."
    try:
        result = llm.predict(prompt)
        return result.strip() if result else "No meaningful information found for this topic."
    except Exception as e:
        return f"Error retrieving topic information: {e}"

# Synthesis Tool
def synthesis_tool(inputs: str) -> str:
    parts = inputs.split("\n", 2)
    if len(parts) < 3:
        return "Error: Insufficient data to synthesize content."
    persona_info, topic_info, article_summary = parts
    return (
        f"Comprehensive Post:\n\n"
        f"**Persona Insights:**\n{persona_info}\n\n"
        f"**Topic Overview:**\n{topic_info}\n\n"
        f"**Related News Article:**\n{article_summary}"
    )

# Register Tools
persona_tool = Tool(
    name="Persona Research Tool",
    func=persona_research_tool,
    description="Use this tool to research detailed information about a persona."
)

topic_tool = Tool(
    name="Topic Research Tool",
    func=topic_research_tool,
    description="Use this tool to research detailed information about a topic."
)

synthesis_tool = Tool(
    name="Synthesis Tool",
    func=synthesis_tool,
    description="Combines persona, topic, and news research into a comprehensive post."
)

tools = [persona_tool, topic_tool, synthesis_tool]
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Initialize Agent
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
)

# News enrichment and post generation
if st.button("Generate Comprehensive Post"):
    if not topic or not persona or not bot_title:
        st.error("Please fill in all the fields.")
    else:
        try:
            # Persona research
            persona_result = persona_research_tool(persona)

            # Topic research
            topic_result = topic_research_tool(topic)

            # News enrichment
            gn = GoogleNews(region='US')
            gn.set_period('7d')
            gn.search(topic)
            results = gn.results()

            if results:
                random_article = random.choice(results)
                article_url = remove_after_ampersand(random_article.get('link'))
                article = Article(article_url)
                article.download()
                article.parse()
                article_summary = f"**Title:** {article.title}\n**Summary:** {article.text[:500]}..."
            else:
                article_summary = "No news articles found for this topic."

            # Synthesize results
            synthesis_input = f"{persona_result}\n{topic_result}\n{article_summary}"
            synthesis_result = synthesis_tool(synthesis_input)

            # Display results
            st.text_area("Comprehensive Post Preview", value=synthesis_result, height=300)

            # Option to post the result as a tweet
            if st.button("Post to Twitter"):
                try:
                    tweet_text = synthesis_result[:280]  # Trim for Twitter's character limit
                    client.create_tweet(text=tweet_text)
                    st.success("Tweet posted successfully!")
                except tweepy.TweepyException as e:
                    st.error(f"Error posting tweet: {e}")
        except Exception as e:
            st.error("An error occurred while generating the post.")
