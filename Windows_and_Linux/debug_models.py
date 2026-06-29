import sys
import os
import logging

# Thêm thư mục hiện tại vào path để import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiprovider import (GeminiProvider, AnthropicProvider, MistralProvider, 
                        OpenRouterProvider, OpenAICompatibleProvider, OllamaProvider)

# Giả lập đối tượng app đơn giản
class MockApp:
    def __init__(self):
        self.config = {"providers": {}}
        self.output_ready_signal = type('obj', (object,), {'emit': lambda self, x: print(f"\n[OUTPUT]: {x}")})()
    
    def save_config(self, config):
        pass

def test_provider(provider_class, name):
    print(f"\n--- Testing {name} ---")
    app = MockApp()
    provider = provider_class(app)
    
    # Yêu cầu nhập API Key nếu cần
    api_key = input(f"Nhập API Key cho {name} (để trống nếu không dùng): ").strip()
    if not api_key and name != "Ollama":
        print(f"Bỏ qua {name} vì không có key.")
        return

    # Cấu hình provider
    config = {"api_key": api_key}
    if name == "OpenAI Compatible":
        config["api_base"] = input("Nhập API Base URL (mặc định cho OpenAI nếu trống): ").strip() or "https://api.openai.com/v1"
        config["api_model"] = input("Nhập model name (mặc định gpt-4o-mini): ").strip() or "gpt-4o-mini"
    
    provider.load_config(config)
    
    instruction = "You are a helpful assistant."
    prompt = "Hello, who are you? Respond in Vietnamese."
    
    print(f"Đang gửi yêu cầu tới {name}...")
    try:
        # Test streaming nếu được yêu cầu
        use_stream = input("Bạn có muốn test streaming không? (y/n): ").lower() == 'y'
        
        if use_stream:
            print("Kết quả (streaming): ", end="", flush=True)
            for chunk in provider.get_response_stream(instruction, prompt):
                print(chunk, end="", flush=True)
            print("\nDone.")
        else:
            response = provider.get_response(instruction, prompt, return_response=True)
            print(f"Kết quả: {response}")
    except Exception as e:
        print(f"Lỗi khi test {name}: {e}")

def main():
    while True:
        print("\n=== AI Model Test Tool ===")
        print("1. Gemini")
        print("2. Anthropic (Claude)")
        print("3. Mistral")
        print("4. OpenRouter")
        print("5. OpenAI Compatible")
        print("6. Ollama (Yêu cầu Ollama đang chạy)")
        print("0. Thoát")
        
        choice = input("Chọn model muốn test (0-6): ")
        
        if choice == '1': test_provider(GeminiProvider, "Gemini")
        elif choice == '2': test_provider(AnthropicProvider, "Anthropic")
        elif choice == '3': test_provider(MistralProvider, "Mistral")
        elif choice == '4': test_provider(OpenRouterProvider, "OpenRouter")
        elif choice == '5': test_provider(OpenAICompatibleProvider, "OpenAI Compatible")
        elif choice == '6': test_provider(OllamaProvider, "Ollama")
        elif choice == '0': break
        else: print("Lựa chọn không hợp lệ.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    main()
