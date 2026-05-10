import pytest
from core.llm import LLMProvider
from core.memory import Historian
from agents.mastermind import Mastermind
from agents.hacker import Hacker

class MockResponse:
    def __init__(self, content):
        self.content = content

class MockLLM(LLMProvider):
    def __init__(self, mock_response_content):
        self.mock_response_content = mock_response_content
        self.last_messages = None
        
    def generate(self, messages, model="gpt-4o", temperature=0.7, tools=None):
        self.last_messages = messages
        return MockResponse(self.mock_response_content)

def test_mastermind_generation(tmpdir):
    historian = Historian(log_dir=str(tmpdir.mkdir("logs")))
    mock_llm = MockLLM('{"family": "Test", "hypothesis": "Do stuff", "execution_mode": "automated"}')
    
    mastermind = Mastermind(llm=mock_llm, historian=historian, persona="white-box")
    
    target_files = {"assignments.html": "<html/>", "home.js": "console.log();"}
    response = mastermind.generate_hypothesis(target_files)
    
    assert "family" in response
    
    # Check that prompt included the target files since it's white-box
    user_prompt = mock_llm.last_messages[1]["content"]
    assert "<html/>" in user_prompt
    assert "console.log();" in user_prompt

def test_mastermind_grey_box(tmpdir):
    historian = Historian(log_dir=str(tmpdir.mkdir("logs")))
    mock_llm = MockLLM('{"family": "Test", "hypothesis": "Do stuff", "execution_mode": "automated"}')
    
    mastermind = Mastermind(llm=mock_llm, historian=historian, persona="grey-box")
    
    target_files = {"assignments.html": "<html/>", "home.js": "console.log();", "consumer.py": "def test(): pass"}
    mastermind.generate_hypothesis(target_files)
    
    user_prompt = mock_llm.last_messages[1]["content"]
    assert "<html/>" in user_prompt
    # grey-box shouldn't see consumer.py
    assert "consumer.py" not in user_prompt
    assert "def test(): pass" not in user_prompt

def test_hacker_code_extraction():
    mock_response = "Here is the code:\n```python\nprint('hello')\n```\nGood luck!"
    mock_llm = MockLLM(mock_response)
    hacker = Hacker(llm=mock_llm)
    
    code = hacker.write_exploit_script('{"hypothesis": "test"}')
    assert code == "print('hello')"

def test_hacker_code_extraction_no_fences():
    mock_response = "print('hello fallback')"
    mock_llm = MockLLM(mock_response)
    hacker = Hacker(llm=mock_llm)
    
    code = hacker.write_exploit_script('{"hypothesis": "test"}')
    assert code == "print('hello fallback')"
