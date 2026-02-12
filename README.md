# manual_evaluation

## Demo
![demo_image](./demo.png)

## Getting Started

### Clone app
```bash
git clone https://github.com/danhtran8989/manual_evaluation.git
cd manual_evaluation
```

### Install dependencies
```bash
pip install -r requirements.txt --force-reinstall
```
### Start App
```python
python app.py
```
App willbe hosted at: `localhost:7860`

## Output
The example output path is `/content/drive/MyDrive/OSAS/osas_chat_bot/manual_test/Danh/user-001/nemotron-3-nano_30b-cloud/P01-1.xlsx`.
THe Tree Directory like below:
```markdown
manual_test/
└── Danh/
    └── user-001/
        ├── gemma3_27b-cloud/
        │   ├── P01-1.xlsx
        │   ├── P01-2.xlsx
        │   └── ...
        ├── gpt-oss_20b-cloud/
        │   ├── P01-1.xlsx
        │   ├── P01-2.xlsx
        │   └── ...
        └── nemotron-3-nano_30b-cloud/
            ├── P01-1.xlsx
            ├── P01-2.xlsx
            └── ...
```
The example output is:
| ID       | Score |
|----------|-------|
| P01-1-01 | 1     |
| P01-1-02 | 1     |
| ... | ...     |
