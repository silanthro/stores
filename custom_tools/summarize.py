from typing import Optional

from dotenv import load_dotenv
from litellm import completion

load_dotenv()

def summarize(text: str, add_request: Optional[str] = None, max_length: Optional[int] = None) -> str:
    """
    Summarize text using Google's Gemini Pro model via LiteLLM.
    
    Args:
        text: The input text to summarize
        add_request: Optional additional request for the summarization
        max_length: Optional maximum length of the summary in words
        
    Returns:
        str: A concise summary of the input text
    """
    

    try:
        length_constraint = f"in no more than {max_length} words" if max_length else ""
        prompt = f"""Please provide a clear and concise summary of the following text {length_constraint}. 

        {add_request}
        
        Text to summarize:
        {text}
        """
        
        response = completion(
            model="gemini/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=max_length * 4 if max_length else None
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        raise Exception(f"Error in text summarization: {str(e)}") from e