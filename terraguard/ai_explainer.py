import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

_cache = {}


# -------------------------------
# INTERNAL: Safe LLM call
# -------------------------------
def _ask_groq(prompt, max_tokens=110):
    try:
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior DevOps engineer. "
                        "Explain infrastructure clearly, accurately, and concisely. "
                        "Focus on purpose, not just listing resources. "
                        "Never hallucinate or assume missing components."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"AI Error: {str(e)}"


# -------------------------------
# SAFETY FILTER (Anti-hallucination)
# -------------------------------
def sanitize_output(output, resources):
    resource_types = [r["type"] for r in resources]

    blocked_terms = {
        "load balancer": "aws_lb",
        "lambda": "aws_lambda_function",
        "cloudfront": "aws_cloudfront_distribution",
        "eks": "aws_eks_cluster",
        "nat gateway": "aws_nat_gateway",
    }

    cleaned = output.lower()

    for term, rtype in blocked_terms.items():
        if term in cleaned and rtype not in resource_types:
            output = output.replace(term, "")

    return output.strip()


# -------------------------------
# SINGLE RESOURCE EXPLANATION
# -------------------------------
def explain_resource(resource):
    key = f"res::{resource['type']}::{resource['name']}"

    if key in _cache:
        return _cache[key]

    prompt = f"""
Explain this Terraform resource in a simple narrative style.

Resource:
{resource['type']} ({resource['name']})

Configuration:
{resource.get('config', {})}

Rules:
- Exactly 2 short sentences
- Plain text only
- Sentence 1: what it creates
- Sentence 2: what it is used for
- Be clear and direct
- Do NOT guess missing dependencies

Example:
It creates a VPC that defines a private network. It is used to host subnets and manage communication.
"""

    output = _ask_groq(prompt, max_tokens=60)

    _cache[key] = output
    return output


# -------------------------------
# FULL INFRA EXPLANATION (FINAL)
# -------------------------------
def explain_infrastructure(resources):
    key = "infra::final_balanced"

    if key in _cache:
        return _cache[key]

    summary = [r["type"] for r in resources]

    prompt = f"""
Explain this Terraform infrastructure in ONE balanced paragraph.

Resources:
{summary}

STRICT RULES:
- Output must be exactly ONE paragraph
- Maximum 3–4 sentences
- Not too long, not too short
- Plain text only
- Explain BOTH:
  1. what infrastructure is created
  2. what it is used for
- Focus on purpose and real-world usage
- ONLY describe resources listed above
- DO NOT add or assume missing components
- DO NOT infer services
- DO NOT use words like "likely", "maybe", "probably"
- Be clear, confident, and natural

Good Example:
It creates a VPC with subnets and internet access using an internet gateway and security controls. It deploys compute and storage resources such as EC2 and S3 to run applications and store data. The infrastructure provides a basic cloud environment for hosting applications with networking, compute, and storage capabilities.
"""

    output = _ask_groq(prompt, max_tokens=110)

    # Safety layer
    output = sanitize_output(output, resources)

    _cache[key] = output
    return output