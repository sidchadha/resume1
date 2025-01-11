import streamlit as st
from openai import OpenAI
from config import OPENAI_API_KEY
from io import BytesIO
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize session state
if 'resume_bullets' not in st.session_state:
    st.session_state.resume_bullets = []
if 'generated' not in st.session_state:
    st.session_state.generated = False
if 'job_description' not in st.session_state:
    st.session_state.job_description = ""

def extract_experience_from_text(text):
    """
    Extract all relevant experience information from text, including headers,
    roles, dates, and bullet points (with or without bullet characters).
    """
    experiences = []
    current_experience = {}
    current_bullets = []
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.rstrip()  # Keep leading whitespace for indentation detection
        
        # Skip truly empty lines
        if not line.strip():
            continue
            
        # Check if it's a header line (RECENT EXPERIENCE, WORK EXPERIENCE, etc.)
        if line.strip().isupper() and len(line.strip()) > 3:
            if current_experience and current_bullets:
                current_experience['bullets'] = current_bullets
                experiences.append(current_experience.copy())
                current_bullets = []
            current_experience = {'section': line.strip()}
            continue
            
        # Check for company name
        if not line.startswith(' ') and len(line.strip()) > 0 and not line.strip().startswith('•') and not line.strip().startswith('o'):
            if current_experience and current_bullets:
                current_experience['bullets'] = current_bullets
                experiences.append(current_experience.copy())
                current_bullets = []
            current_experience = {'company': line.strip()}
            continue
            
        # Check for role and date information
        if 'company' in current_experience and not line.strip().startswith('•') and not line.strip().startswith('o'):
            # Look for date patterns
            if any(month in line for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                current_experience['dates'] = line.strip()
                continue
            # If it's not a date and not a bullet, it's likely a role
            if not current_experience.get('role'):
                current_experience['role'] = line.strip()
                continue
                
        # Handle bullet points and regular lines as content
        line_content = line.strip()
        if line_content:
            # Remove bullet characters if they exist
            if line_content.startswith('•') or line_content.startswith('o'):
                line_content = line_content[1:].strip()
            # Add line as a bullet if it has content
            if line_content:
                current_bullets.append(line_content)
    
    # Don't forget to add the last experience
    if current_experience and current_bullets:
        current_experience['bullets'] = current_bullets
        experiences.append(current_experience)
    
    return experiences

def get_tailored_bullets(job_description, reference_bullets):
    """
    Generate tailored resume bullets based on job description and reference experience.
    """
    # First, analyze the job description to extract key requirements
    analysis_prompt = f"""
    Analyze the following job description and extract:
    1. Key technical skills required
    2. Important soft skills mentioned
    3. Primary responsibilities
    4. Project types or domains mentioned
    5. Tools or technologies emphasized
    
    Job Description:
    {job_description}
    
    Format your response as a concise list of key points that should be emphasized in the resume bullets.
    """
    
    # Get job analysis
    analysis_response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a professional job description analyst."},
            {"role": "user", "content": analysis_prompt}
        ],
        temperature=0.5,
        max_tokens=500
    )
    
    job_analysis = analysis_response.choices[0].message.content
    
    experiences = extract_experience_from_text(reference_bullets)
    formatted_experiences = []
    for exp in experiences:
        if 'company' in exp:
            section = []
            section.append(f"\n{exp['company']}")
            if 'role' in exp:
                section.append(exp['role'])
            if 'dates' in exp:
                section.append(exp['dates'])
            if 'bullets' in exp:
                section.extend([f"• {bullet}" for bullet in exp['bullets']])
            formatted_experiences.append('\n'.join(section))
    
    formatted_text = '\n\n'.join(formatted_experiences)
    
    # Enhanced prompts that incorporate job analysis
    gs_prompt = f"""
    Create EXACTLY 8 bullet points for Goldman Sachs (Marcus focus) that specifically address the following job requirements:
    
    Job Analysis:
    {job_analysis}
    
    Reference Experience:
    {formatted_text}

    Guidelines:
    1. Each bullet MUST start with a strong action verb
    2. Each bullet MUST be about Goldman Sachs/Marcus (NO mentions of Merrill or Bank of America)
    3. Each bullet MUST address specific requirements from the job description above
    4. Focus on matching your experiences to the job's needs
    5. Include relevant technical skills and tools mentioned in the job posting
    6. Highlight achievements that demonstrate required competencies
    7. Use metrics that showcase impact in areas important to this role

    CRITICAL: Tailor each bullet to specifically match the job requirements while maintaining authenticity.
    
    Example format:
    • Implemented cloud-based API architecture for Marcus lending platform, achieving 30% improved processing time and aligning with organization's digital transformation goals
    """

    boa_prompt = f"""
    Create EXACTLY 8 bullet points for Bank of America (Merrill focus) that specifically address the following job requirements:
    
    Job Analysis:
    {job_analysis}
    
    Reference Experience:
    {formatted_text}

    Guidelines:
    1. Each bullet MUST start with a strong action verb
    2. Each bullet MUST be about Merrill/Bank of America (NO mentions of Marcus or Goldman Sachs)
    3. Each bullet MUST address specific requirements from the job description above
    4. Focus on matching your experiences to the job's needs
    5. Include relevant technical skills and tools mentioned in the job posting
    6. Highlight achievements that demonstrate required competencies
    7. Use metrics that showcase impact in areas important to this role

    CRITICAL: Tailor each bullet to specifically match the job requirements while maintaining authenticity.
    
    Example format:
    • Developed real-time analytics dashboard for Merrill Edge platform, reducing decision-making time by 25% and improving team efficiency
    """

    system_prompt = """You are a professional resume writer specialized in tailoring experience to job requirements.
    For each bullet point:
    1. Focus on experiences that directly match the job requirements
    2. Emphasize relevant skills and technologies mentioned in the job posting
    3. Quantify achievements in ways that matter for the target role
    4. Maintain clear company separation and authenticity
    5. Use language that resonates with the industry and role"""

    # Get Goldman Sachs bullets
    gs_response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": gs_prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    
    # Get Bank of America bullets
    boa_response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": boa_prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    
    # Process Goldman Sachs bullets
    gs_bullets = [b.strip() for b in gs_response.choices[0].message.content.split('\n') 
                 if b.strip().startswith('•')][:8]
    
    # Process Bank of America bullets
    boa_bullets = [b.strip() for b in boa_response.choices[0].message.content.split('\n') 
                  if b.strip().startswith('•')][:8]
    
    # Validate bullet counts
    if len(gs_bullets) != 8 or len(boa_bullets) != 8:
        raise Exception("Failed to generate correct number of unique bullets for each company")
        
    return gs_bullets + boa_bullets

def sanitize_text(text):
    """Replace Unicode characters with ASCII equivalents"""
    text = str(text)
    replacements = {
        '•': '-',
        ''': "'",
        ''': "'",
        '"': '"',
        '"': '"',
        '–': '-',
        '—': '-',
        '…': '...',
        '\u2022': '-',
        '\u2019': "'",
        '\u2013': "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def create_pdf(name, contact_info, work_experience, education):
    """Generate a professional PDF resume using ReportLab"""
    # Register Times New Roman fonts
    pdfmetrics.registerFont(TTFont('TimesNewRoman', 'fonts/TIMES.TTF'))
    pdfmetrics.registerFont(TTFont('TimesNewRoman-Bold', 'fonts/TIMESBD.TTF'))
    
    try:
        buffer = BytesIO()
        
        # Create the PDF object
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=1*inch,
            leftMargin=1*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Define styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Name',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=8,
            alignment=1,
            fontName='TimesNewRoman-Bold'
        ))
        styles.add(ParagraphStyle(
            name='Contact',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=20,
            alignment=1,
            leading=14,
            fontName='TimesNewRoman'
        ))
        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontSize=12,
            spaceBefore=15,
            spaceAfter=10,
            fontName='TimesNewRoman-Bold',
            textTransform='uppercase'
        ))
        styles.add(ParagraphStyle(
            name='CompanyHeader',
            parent=styles['Normal'],
            fontSize=11,
            fontName='TimesNewRoman-Bold',
            spaceBefore=10,
            spaceAfter=2,
            leading=15
        ))
        styles.add(ParagraphStyle(
            name='JobTitle',
            parent=styles['Normal'],
            fontSize=11,
            fontName='TimesNewRoman-Bold',
            spaceAfter=6,
            leading=15
        ))
        styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=styles['Normal'],
            fontSize=10,
            leftIndent=15,
            firstLineIndent=-8,
            spaceBefore=2,
            spaceAfter=2,
            leading=15,
            fontName='TimesNewRoman',
            bulletIndent=0
        ))
        
        elements = []
        
        # Add name
        elements.append(Paragraph(name, styles['Name']))
        
        # Add contact info
        elements.append(Paragraph(contact_info, styles['Contact']))
        
        # Add Work Experience section
        elements.append(Paragraph('WORK EXPERIENCE', styles['SectionHeader']))
        
        # Add each job
        for job in work_experience:
            company_table = Table([[job['company'], job['dates']]], 
                                colWidths=[4*inch, 2.5*inch])
            company_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, -1), 'TimesNewRoman-Bold', 11),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ]))
            elements.append(company_table)
            
            elements.append(Paragraph(job['title'], styles['JobTitle']))
            
            for bullet in job['bullets']:
                if bullet.get('selected', False):
                    bullet_text = '• ' + sanitize_text(bullet.get('text', '')).strip()
                    elements.append(Paragraph(bullet_text, styles['BulletPoint']))
            
            elements.append(Spacer(1, 10))
        
        # Add Education section
        elements.append(Paragraph('EDUCATION', styles['SectionHeader']))
        elements.append(Paragraph(education['degree'], styles['CompanyHeader']))
        elements.append(Paragraph(education['school'], styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
        
    except Exception as e:
        raise Exception(f"PDF generation error: {str(e)}")

def main():
    st.title('Resume Builder')
    
    # Job Description Input
    if not st.session_state.generated:
        job_description = st.text_area('Paste the job description here:', 
                                     value=st.session_state.job_description)
        st.session_state.job_description = job_description
        
        if st.button('Generate Resume'):
            try:
                # Read reference bullets from file
                try:
                    with open('bullets.txt', 'r', encoding='utf-8') as file:
                        reference_bullets = file.read()
                except FileNotFoundError:
                    st.error("Could not find bullets.txt file. Please ensure it exists in the correct location.")
                    return
                except Exception as e:
                    st.error(f"Error reading bullets.txt: {str(e)}")
                    return
                
                if not reference_bullets.strip():
                    st.error("bullets.txt file is empty. Please add reference experience information.")
                    return
                    
                # Get new bullets from OpenAI
                new_bullets = get_tailored_bullets(job_description, reference_bullets)
                
                if len(new_bullets) != 16:
                    st.error(f"Error: Generated {len(new_bullets)} bullets instead of 16. Please try again.")
                    return
                
                # Store in session state with all bullets selected by default
                st.session_state.resume_bullets = [
                    {'text': bullet.lstrip('• '), 'selected': True, 'editable': bullet.lstrip('• ')} 
                    for bullet in new_bullets
                ]
                st.session_state.generated = True
                st.rerun()
                
            except Exception as e:
                st.error(f"Error generating bullets: {str(e)}")
    
    # Selection Interface
    else:
        st.subheader('Select Bullets for Your Resume')
        
        if st.button('Start Over'):
            st.session_state.generated = False
            st.session_state.job_description = ""
            st.rerun()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Goldman Sachs Bullets")
            # Display exactly 8 Goldman Sachs bullets
            for i in range(8):
                if i < len(st.session_state.resume_bullets):
                    st.session_state.resume_bullets[i]['selected'] = st.checkbox(
                        st.session_state.resume_bullets[i]['text'],
                        value=st.session_state.resume_bullets[i]['selected'],
                        key=f'gs_{i}'
                    )
        
        with col2:
            st.subheader("Bank of America Bullets")
            # Display exactly 8 Bank of America bullets
            for i in range(8, 16):
                if i < len(st.session_state.resume_bullets):
                    st.session_state.resume_bullets[i]['selected'] = st.checkbox(
                        st.session_state.resume_bullets[i]['text'],
                        value=st.session_state.resume_bullets[i]['selected'],
                        key=f'boa_{i}'
                    )
        
        if st.button('Generate PDF'):
            # Resume data structure
            resume_data = {
                'name': 'Siddharth Chadha',
                'contact_info': '309 Gold Street, Brooklyn, NY • +1 631-949-2013 • sidchadha@onmail.com',
                'work_experience': [
                    {
                        'company': 'Goldman Sachs',
                        'title': 'Vice President - Product Manager',
                        'dates': 'Jan 2022 - Present',
                        'bullets': st.session_state.resume_bullets[:8]  # Exactly first 8 bullets
                    },
                    {
                        'company': 'Bank of America',
                        'title': 'Vice President - Product Manager',
                        'dates': 'Jan 2015 - Dec 2021',
                        'bullets': st.session_state.resume_bullets[8:16]  # Exactly next 8 bullets
                    }
                ],
                'education': {
                    'degree': 'Double Major - Economics & Finance',
                    'school': 'Stony Brook University'
                }
            }
            
            try:
                pdf_bytes = create_pdf(
                    resume_data['name'],
                    resume_data['contact_info'],
                    resume_data['work_experience'],
                    resume_data['education']
                )
                
                st.download_button(
                    label="Download PDF Resume",
                    data=pdf_bytes,
                    file_name="tailored_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")

if __name__ == '__main__':
    main()
