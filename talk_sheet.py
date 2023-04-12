import os
import pickle
import streamlit as st
import tempfile
import pandas as pd
import asyncio

# Import modules needed for building the chatbot application
from streamlit_chat import message
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.document_loaders.csv_loader import CSVLoader
from langchain.prompts import PromptTemplate
from langchain.vectorstores import FAISS
from langchain.text_splitter import CharacterTextSplitter

# Set the Streamlit page configuration, including the layout and page title/icon
st.set_page_config(layout="wide", page_icon="contents\logo_site.png", page_title="Talk-Sheet")

# Display the header for the application using HTML markdown
st.markdown(
    "<h1 style='text-align: center;'>Talk-Sheet, Talk with your  sheet-data ! 💬</h1>",
    unsafe_allow_html=True)

# Allow the user to enter their OpenAI API key
user_api_key = st.sidebar.text_input(
    label="#### Your OpenAI API key 👇",
    placeholder="Paste your openAI API key, sk-",
    type="password")

async def main():
    
    # Check if the user has entered an OpenAI API key
    if user_api_key == "":
        
        # Display a message asking the user to enter their API key
        st.markdown(
            "<div style='text-align: center;'><h4>Enter your OpenAI API key to start chatting 😉</h4></div>",
            unsafe_allow_html=True)
        
    else:
        # Set the OpenAI API key as an environment variable
        os.environ["OPENAI_API_KEY"] = user_api_key
        
        # Allow the user to upload a CSV file
        uploaded_file = st.sidebar.file_uploader("", type="csv", label_visibility="hidden")
        
        # If the user has uploaded a file, display it in an expander
        if uploaded_file is not None:
            def show_user_file(uploaded_file):
                file_container = st.expander("Your CSV file :")
                shows = pd.read_csv(uploaded_file)
                uploaded_file.seek(0)
                file_container.write(shows)
                
            show_user_file(uploaded_file)
            
        # If the user has not uploaded a file, display a message asking them to do so
        else :
            st.sidebar.info(
            "👆 Upload your CSV file to get started, "
            "sample : [fishfry-locations.csv](https://drive.google.com/file/d/18i7tN2CqrmoouaSqm3hDfAk17hmWx94e/view?usp=sharing)" 
            )
    
        if uploaded_file :
            try :
                # Define an asynchronous function for storing document embeddings using Langchain and FAISS
                async def storeDocEmbeds(file, filename):
                    
                    # Write the uploaded file to a temporary file
                    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp_file:
                        tmp_file.write(file)
                        tmp_file_path = tmp_file.name

                    # Load the data from the CSV file using Langchain
                    loader = CSVLoader(file_path=tmp_file_path, encoding="utf-8")
                    data = loader.load()
                    
                    # Split the text into smaller chunks for easier processing
                    splitter = CharacterTextSplitter(separator="\n",chunk_size=1500, chunk_overlap=0)
                    chunks = splitter.split_documents(data)
                    
                    # Create an embeddings object using Langchain
                    embeddings = OpenAIEmbeddings()
                    
                    # Store the embeddings vectors using FAISS
                    vectors = FAISS.from_documents(chunks, embeddings)
                    os.remove(tmp_file_path)

                    # Save the vectors to a pickle file
                    with open(filename + ".pkl", "wb") as f:
                        pickle.dump(vectors, f)

                # Define an asynchronous function for retrieving document embeddings
                async def getDocEmbeds(file, filename):
                    
                    # Check if embeddings vectors have already been stored in a pickle file
                    if not os.path.isfile(filename + ".pkl"):
                        # If not, store the vectors using the storeDocEmbeds function
                        await storeDocEmbeds(file, filename)
                    
                    # Load the vectors from the pickle file
                    with open(filename + ".pkl", "rb") as f:
                        global vectores
                        vectors = pickle.load(f)
                        
                    return vectors

                # Define an asynchronous function for conducting conversational chat using Langchain
                async def conversational_chat(query):
                    
                    # Use the Langchain ConversationalRetrievalChain to generate a response to the user's query
                    result = qa({"question": query, "chat_history": st.session_state['history']})
                    
                    # Add the user's query and the chatbot's response to the chat history
                    st.session_state['history'].append((query, result["answer"]))
                    
                    # Print the chat history for debugging purposes
                    print("Log: ")
                    print(st.session_state['history'])
                    
                    return result["answer"]

                # Define a template for prompts to be used by the Langchain ConversationalRetrievalChain
                prompt_template = (
                "You are Talk-Sheet, a user-friendly chatbot designed to assist users by engaging in conversations based on data from CSV or Excel files. "
                "Your knowledge comes from:"

                "{context}"

                "Help users by providing relevant information from the data in their files. Answer their questions accurately and concisely. "
                "If the user's specific issue or need cannot be addressed with the available data, "
                "empathize with their situation and suggest that they may need to seek assistance elsewhere. "
                "Always maintain a friendly and helpful tone. "
                "If you don't know the answer to a question, truthfully say you don't know."
                "answers the user's question in the same language as the user"
          
                "Human: {question} "

                "Talk-Sheet: "
                )
                
                # Create a PromptTemplate object using the prompt_template defined above
                PROMPT = PromptTemplate(template=prompt_template, input_variables=["context","question"])

                # Set up sidebar with various options
                with st.sidebar.expander("🛠️ Settings", expanded=False):
                    
                    # Add a button to reset the chat history
                    if st.button("Reset Chat"):
                        st.session_state['reset_chat'] = True

                    # Allow the user to select a chatbot model to use
                    MODEL = st.selectbox(label='Model', options=['gpt-3.5-turbo','gpt-4'])

                # If the chat history has not yet been initialized, do so now
                if 'history' not in st.session_state:
                    st.session_state['history'] = []

                # If the chatbot is not yet ready to chat, set the "ready" flag to False
                if 'ready' not in st.session_state:
                    st.session_state['ready'] = False
                    
                # If the "reset_chat" flag has not been set, set it to False
                if 'reset_chat' not in st.session_state:
                    st.session_state['reset_chat'] = False
                
                        # If a CSV file has been uploaded
                if uploaded_file is not None:

                    # Display a spinner while processing the file
                    with st.spinner("Processing..."):

                        # Read the uploaded CSV file
                        uploaded_file.seek(0)
                        file = uploaded_file.read()
                        
                        # Generate embeddings vectors for the file
                        vectors = await getDocEmbeds(file, uploaded_file.name)
                        
                        # Use the Langchain ConversationalRetrievalChain to set up the chatbot
                        qa = ConversationalRetrievalChain.from_llm(ChatOpenAI(model_name=MODEL), 
                                                                   retriever=vectors.as_retriever(), 
                                                                   qa_prompt=PROMPT,return_source_documents=False)

                    # Set the "ready" flag to True now that the chatbot is ready to chat
                    st.session_state['ready'] = True

                # If the chatbot is ready to chat
                if st.session_state['ready']:

                    # If the chat history has not yet been initialized, initialize it now
                    if 'generated' not in st.session_state:
                        st.session_state['generated'] = ["Hello ! Ask me anything about " + uploaded_file.name + " 🤗"]

                    if 'past' not in st.session_state:
                        st.session_state['past'] = ["Hey Talk-Sheet !"]

                    # Create a container for displaying the chat history
                    response_container = st.container()
                    
                    # Create a container for the user's text input
                    container = st.container()

                    with container:
                        
                        # Create a form for the user to enter their query
                        with st.form(key='my_form', clear_on_submit=True):
                            
                            user_input = st.text_input("Query:", placeholder="Talk about your csv data here (:", key='input')
                            submit_button = st.form_submit_button(label='Send')
                            
                            # If the "reset_chat" flag has been set, reset the chat history and generated messages
                            if st.session_state['reset_chat']:
                                
                                st.session_state['history'] = []
                                st.session_state['past'] = ["Hey!"]
                                st.session_state['generated'] = ["Welcome! You can now ask any questions regarding " + uploaded_file.name]
                                response_container.empty()
                                st.session_state['reset_chat'] = False

                        # If the user has submitted a query
                        if submit_button and user_input:
                            
                            # Generate a response using the Langchain ConversationalRetrievalChain
                            output = await conversational_chat(user_input)
                            
                            # Add the user's input and the chatbot's output to the chat history
                            st.session_state['past'].append(user_input)
                            st.session_state['generated'].append(output)

                    # If there are generated messages to display
                    if st.session_state['generated']:
                        
                        # Display the chat history
                        with response_container:
                            
                            for i in range(len(st.session_state['generated'])):
                                message(st.session_state["past"][i], is_user=True, key=str(i) + '_user', avatar_style="big-smile")
                                message(st.session_state["generated"][i], key=str(i), avatar_style="thumbs")
            except Exception as e:
                st.error(f"Error: {str(e)}")
    # Create an expander for the "About" section
    about = st.sidebar.expander("About Talk-Sheet 🤖")
    
    # Write information about the chatbot in the "About" section
    about.write("#### Talk-Sheet is a user-friendly chatbot designed to assist users by engaging in conversations based on data from CSV or excel files. 📄")
    about.write("#### Ideal for various purposes and users, Talk-Sheet provides a simple yet effective way to interact with your sheet-data. 🌐")
    about.write("#### Powered by Langchain, OpenAI and Streamlit Talk-Sheet offers a seamless and personalized experience. ⚡")
    about.write("#### Source code : yvann-hub/Talk-Sheet")

#Run the main function using asyncio
if __name__ == "__main__":
    asyncio.run(main())

