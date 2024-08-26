import hmac
import streamlit as st
import tweepy
import os
import random
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

def remove_after_ampersand(s):
    return s.split('&', 1)[0]

# Auth functions
def check_password():
    """Returns `True` if the user has entered the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        env_password = app_password  # Fetch the password from environment variable
        if env_password is None:
            st.error("Environment variable 'TWITTER_NEWS_APP_PASSWORD' not set.")
            return
        
        if hmac.compare_digest(st.session_state.get("password", ""), env_password):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct"):
        return True

    # Show input for password.
    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state.password_correct:
        st.error("😕 Password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if check_password is not True.

# Streamlit app
st.title("news bot")

# Input fields
topic = st.text_input("Enter the topic for news search")
persona = st.text_input("Enter the persona")
bot_title = st.text_input("Enter bot title")

# Create a form to group input and buttons together
with st.form("tweet_form"):
    # Button to generate tweet preview
    generate_button = st.form_submit_button("Generate Preview")

    if generate_button:
        if not topic or not persona or not bot_title:
            st.error("Please fill in all the fields.")
        else:
            # Initialize GoogleNews object
            gn = GoogleNews(region='US')
            gn.set_period('1d')
            gn.search(topic)

            # Get the search results
            results = gn.results()

            # Check if results are available
            if results:
                # Randomly select an article
                random_article = random.choice(results)

                # Extract the URL of the selected article
                article_url = random_article.get('link')
                clean_url = remove_after_ampersand(article_url)

                # Initialize Newspaper Article object
                article = Article(clean_url)
                
                try:
                    article.download()
                    article.parse()

                    # Extract the text of the article
                    article_text = article.text
                    article_title = article.title
                    article_source = article.canonical_link

                    # Define the prompt
                    persona_string = f"You are a {persona} reading the news."
                    full_string = f"{persona_string} Write an engaging, ultra captivating post that captures the essence of the news article provided. Keep the post under 300 characters. Please consider the following: {article_text} {article_title} {article_source}"

                    gn.clear()

                    # Generate content using Gemini
                    model = genai.GenerativeModel('gemini-pro')
                    response = model.generate_content(full_string)

                    # Create tweet text
                    tweet_text = f"{response.text}\n\n[-_-] {bot_title} built by jake"

                    # Display the tweet preview
                    st.subheader("Preview")
                    st.write(tweet_text)

                    # Store the tweet text in session state for persistence
                    st.session_state.tweet_text = tweet_text

                except Exception as e:
                    st.error(f"Error extracting article text: {e}")
            else:
                st.error("No results found.")

        # Display the submit button
        submit_button = st.form_submit_button("Submit Tweet")

        if submit_button and "tweet_text" in st.session_state:
            # Attempt to post the tweet
            try:
                client.create_tweet(text=st.session_state.tweet_text)
                st.success("Tweet posted successfully")
            except tweepy.TweepyException as e:
                st.error(f"Error posting tweet: {e}")
