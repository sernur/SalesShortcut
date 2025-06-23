import sys
import os

# Add the main project to Python path
sys.path.append('/Users/xskills/Development/Python/Hackathons/SalesShortcut')

# Import the function and template
from sdr.sdr.sub_agents.outreach_email_agent.tools.create_pdf_offer import create_sales_proposal_pdf
from sdr.sdr.sub_agents.outreach_email_agent.sub_agents.specification_creator.spec_template import SPEC_MARKDOWN_TEMPLATE

result = create_sales_proposal_pdf(SPEC_MARKDOWN_TEMPLATE)
print(f'PDF created at: {result}')