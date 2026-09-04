import streamlit as st
import os
import glob
import yaml

st.set_page_config(page_title="Antigravity Operations Hub", layout="wide")

st.title("Antigravity Operations Hub")
st.markdown("Your centralized database of Standard Operating Procedures (SOPs).")

skills_dir = r"G:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills"

# Find all SKILL.md files
skill_files = glob.glob(os.path.join(skills_dir, "*", "SKILL.md"))

if not skill_files:
    st.warning("No SOPs found in the skills directory.")
else:
    # Sidebar navigation
    st.sidebar.title("SOP Database")
    
    sops = {}
    for filepath in skill_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Parse YAML frontmatter
            name = os.path.basename(os.path.dirname(filepath))
            body = content
            
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2]
                    try:
                        meta = yaml.safe_load(frontmatter)
                        name = meta.get("name", name)
                    except:
                        pass
                        
            # Categorize based on Track
            category = "General"
            if "sports" in name.lower():
                category = "Sports Cards"
            elif "media" in name.lower():
                category = "Content Creation"
                
            display_name = name.replace("-", " ").title()
            
            if category not in sops:
                sops[category] = {}
            sops[category][display_name] = body

    # Category Selection
    selected_category = st.sidebar.selectbox("Select Track:", list(sops.keys()))
    
    # SOP Selection
    selected_sop = st.sidebar.radio("Select SOP:", list(sops[selected_category].keys()))
    
    # Display content
    st.markdown("---")
    if selected_sop:
        st.markdown(sops[selected_category][selected_sop])
