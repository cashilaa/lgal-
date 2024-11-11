from flask import Flask, render_template, request
from main import process_text

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    redacted_text = None
    error = None
    
    if request.method == 'POST':
        # Get user input from form
        user_text = request.form.get('user_text', '')
        
        try:
            # Process text for PII removal
            redacted_text = process_text(user_text)
        except Exception as e:
            error = f"An error occurred while processing text: {e}"
    
    return render_template('index.html', redacted_text=redacted_text, error=error)

if __name__ == '__main__':
    app.run(debug=True)
