from langchain_groq import ChatGroq
from core.env import load_project_env

load_project_env()

fast_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
powerful_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
