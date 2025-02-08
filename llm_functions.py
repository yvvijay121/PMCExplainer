import openai, re
from pydantic import BaseModel

def modify_text(text):
    # Your modified regex pattern
    pattern = r'<>([^<>]+)<>'

    # Function to replace numbers with the desired format
    def replace_numbers(match):
        parts = match.group(1).split(',')
        modified_parts = []
        
        for part in parts:
            print(part)
            if '–' in part:  # Handle ranges
                start, end = map(int, part.split('–'))
                modified_parts.extend([f'<a href="#R{num}" class="usa-link" aria-describedby="R{num}" aria-expanded="false">{num}</a>' for num in range(start, end + 1)])
            else:
                modified_parts.append(f'<a href="#R{int(part.strip())}" class="usa-link" aria-describedby="R{int(part.strip())}" aria-expanded="false">{int(part.strip())}</a>')
        
        return '<sup>' + ','.join(modified_parts) + '</sup>'

    # Replace the matches in the original text
    modified_text = re.sub(pattern, replace_numbers, text)
    
    return modified_text

def process_review(content):
    # Remove surrounding ```
    content = content.replace("```", "")
    # Split the content by newline characters
    lines = content.split('\n')
    # Remove empty strings from the list
    lines = [line for line in lines if line.strip()]

    error = False
    lines[0] = f"<h2>{lines[0]}</h2>"
    for i in range(1,len(lines)):
        if lines[i].count("!!!") % 2 != 0 and lines[i].count("<>") % 2 != 0:
            error = True
            break
        else:
            # lines[i] = lines[i].replace("``", "<span class=\"ai-gen\">", 1).replace("``", "</span>", 1)
            lines[i] = modify_text(lines[i])
            # lines[i] = lines[i].replace("<>", "<sup>", 1).replace("<>", "</sup>", 1)
            lines[i] = f"<p>{lines[i]}</p>"
    if not error:
        content = ''.join(lines)
    else:
        content = "Error in formatting the content."
    return content

class KeywordExtractionRequest(BaseModel):
    keywords: list[str]


class ComprehensionStatement(BaseModel):
    statement_text: str
    comprehension_level: int

    def __str__(self):
        # Manually create a dictionary representation
        return str(
            {
                "statement_text": self.statement_text,
                "comprehension_level": self.comprehension_level,
            }
        )


class Paragraph(BaseModel):
    text: str


class ResponseType(BaseModel):
    statements: list[ComprehensionStatement]

    def __str__(self):
        # Manually create a list of dictionary representations for each statement
        statements_dict = [statement.to_dict() for statement in self.statements]
        return str({"statements": statements_dict})


def parse_html_for_keywords(text_content, openai_api_key):
    # Initialize OpenAI API
    client = openai.Client(api_key=openai_api_key)

    # Define the prompt for OpenAI

    # Call OpenAI API to get structured output
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Please analyze the provided HTML content of the research paper and extract all technical, medical, and scientific terms. Only include terms that a layperson would not know the definition of.",
            },
            {"role": "user", "content": text_content},
        ],
        response_format=KeywordExtractionRequest,
        temperature=0,
        max_tokens=16384,
    )

    return completion.choices[0].message.parsed.keywords


def comprehension_check(text_content, key):
    client = openai.Client(api_key=key)

    prompt = """Given the abstract of a research paper, generate a set of six statements designed to assess the reader's understanding of the paper.
    Based on the response of the user on a scale of 1 to 6, the paper will be modified to their skill and reading level.
    The statements should range in difficulty from beginner to advanced, covering the following levels:

    1. Beginner Level: A statement that tests basic comprehension of the abstract's main idea or purpose.
    2. Intermediate Level 1: A statement that requires the reader to identify key terms or concepts mentioned in the abstract.
    3. Intermediate Level 2: A statement that asks the reader to explain the significance of the research findings in simple terms.
    4. Advanced Level 1: A statement that challenges the reader to analyze the methodology or approach used in the research.
    5. Advanced Level 2: A statement that prompts the reader to evaluate the implications of the research findings within the broader context of the field.
    6. Expert Level: A statement that encourages the reader to critique the research design or suggest potential improvements or future research directions.

    Make sure each statement is clear and directly related to the content of the abstract."""

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text_content},
        ],
        response_format=ResponseType,
        max_tokens=16384,
    )

    return completion.choices[0].message.parsed.statements


def rewrite_comprehension(text_content, comprehension_num, key):
    client = openai.Client(api_key=key)

    instruction_list = [
        "provide a simplified explanation of the section using accessible language, breaking down complex terms and ideas into layman's terms with real-world examples.",
        "introduce key definitions and contextual explanations for essential terms, ensuring the reader gains a foundational grasp of the concepts.",
        "clarify the significance of the section by explaining why the concepts are important and how they contribute to the broader research topic.",
        "expand on the methodology, approach, or reasoning behind the section, offering a deeper look into how the information was derived or structured.",
        "discuss the broader implications of the section, relating it to trends in the field, real-world applications, or potential challenges in interpretation.",
        "critically evaluate the section by identifying areas of potential refinement, suggesting alternative interpretations, or proposing directions for future research.",
    ]

    base_prompt = f"""Given a section of a research paper and a reader's self-assessed understanding on a scale of 1 to 6, extend the section to enhance clarity and depth in areas where the reader lacks understanding.
    The extension should be tailored to the specific level indicated by the reader, ensuring that the elaboration is neither too simplistic nor too advanced.
    
    Based on the reader's self-assessment, {instruction_list[comprehension_num-1]}
    
    Formatting Requirement:
        - **Additive Only:** All AI-generated explanations must be _added_ to the existing text rather than replacing or altering any original content.
        - **Distinct Formatting:** Surround all AI-generated additions with triple exclamation points (!!!) to clearly distinguish them from the original text.
        - **Preserve Citations:** Do _not_ modify, insert text within, or remove any content inside markers formatted as "<>citation<>". Any AI-generated additions must be placed outside of these citation markers."""

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": base_prompt},
            {"role": "user", "content": text_content},
        ],
        max_tokens=16384,
    )
    return process_review(completion.choices[0].message.content)