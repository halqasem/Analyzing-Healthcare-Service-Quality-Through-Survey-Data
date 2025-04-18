import pandas as pd
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, ctx
import numpy as np
import os # Import the os module

# --- 1. Load and Prepare Data ---
# Get the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the data file relative to the script directory
data_path = os.path.join(script_dir, '..', 'data', 'cleaned', 'cleaned_patient_survey_data.csv')

try:
    # Use the constructed data_path
    df_orig = pd.read_csv(data_path)
    print(f"Data loaded successfully from: {data_path}")
except FileNotFoundError:
    print(f"Error: {data_path} not found. Please ensure the file exists at this location.")
    exit() # Exit if data can't be loaded

df = df_orig.copy()

# Define columns
care_satisfaction_cols = [
    'satisfaction_waiting_time', 'Time with the health provider', 'Privacy during examination',
    'Staff attitude', 'Opening hours of the facility', 'Quality of the advice and information',
    'satisfaction_procedure_treatment', 'overall_satisfaction_rating'
]
facility_satisfaction_cols = [
    'facility_cleanliness_rating', 'facility_condition_rating', 'facility_info_displayed_rating',
    'facility_private_talk_spaces_rating', 'facility_ease_of_movement_rating', 'facility_waiting_comfort_rating'
]
filter_cols = ['health_facility', 'respondent_sex']
all_satisfaction_cols = care_satisfaction_cols + facility_satisfaction_cols

# Check if columns exist
missing_cols = [col for col in all_satisfaction_cols + filter_cols if col not in df.columns]
if missing_cols:
    print(f"Error: The following required columns are missing from the data: {missing_cols}")
    print("Please check the column names in the CSV file.")
    exit()

# --- 2. Data Cleaning and Mapping ---
# Define mapping for qualitative satisfaction (adjust keys based on actual data)
satisfaction_mapping = {
    'Satisfied': 3,
    'somewhat satisfied': 2,
    'Dissatisfied': 1,
    # Add mappings for facility columns if they use text like 'Excellent', 'Good', 'Poor'
    'Excellent': 3, # Example
    'Good': 2,      # Example
    'Fair': 1,      # Example
    'Poor': 0       # Example
}

# Apply mapping ONLY to columns that are not already numeric
print("\nApplying numeric mapping...")
for col in all_satisfaction_cols:
    if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
        print(f"Mapping column: {col}")
        df[col] = df[col].replace(satisfaction_mapping)
        df[col] = pd.to_numeric(df[col], errors='coerce')
        if df[col].isnull().any():
             print(f"  Warning: Some values in {col} could not be mapped and became NaN.")
    elif col in df.columns:
         if not pd.api.types.is_numeric_dtype(df[col]):
             df[col] = pd.to_numeric(df[col], errors='coerce')
             if df[col].isnull().any():
                 print(f"  Warning: Some non-numeric values found in supposedly numeric column {col} became NaN.")

print("Mapping complete.")
print("\nData types after mapping:")
print(df[all_satisfaction_cols].dtypes)


# --- 3. Prepare Options for Filters ---
facility_options = [{'label': 'All Facilities', 'value': 'all'}] + \
                   [{'label': fac, 'value': fac} for fac in sorted(df['health_facility'].dropna().unique())]
sex_options = [{'label': 'All Sexes', 'value': 'all'}] + \
              [{'label': sex, 'value': sex} for sex in sorted(df['respondent_sex'].dropna().unique())]

# --- 4. Initialize Dash App ---
app = dash.Dash(__name__)
server = app.server # Expose server for potential deployment platforms

# --- 5. Define App Layout ---
app.layout = html.Div([
    html.H1("Patient Satisfaction Dashboard"),

    html.Div([
        html.Div([
            html.Label("Select Health Facility:"),
            dcc.Dropdown(
                id='facility-dropdown',
                options=facility_options,
                value=['all'], # Default value
                multi=True # Allow multi-select
            ),
        ], style={'width': '48%', 'display': 'inline-block', 'paddingRight': '10px'}),

        html.Div([
            html.Label("Select Respondent Sex:"),
            dcc.Dropdown(
                id='sex-dropdown',
                options=sex_options,
                value=['all'], # Default value
                multi=True # Allow multi-select
            ),
        ], style={'width': '48%', 'display': 'inline-block', 'paddingLeft': '10px'})
    ]),

    html.Button('Reset Filters', id='reset-button', n_clicks=0, style={'marginTop': '10px', 'marginBottom': '10px'}),

    html.Div(id='summary-card', style={'padding': '10px', 'border': '1px solid #ddd', 'borderRadius': '5px', 'marginBottom': '10px'}),

    html.Div([
        html.Div([
            dcc.Graph(id='care-satisfaction-chart')
        ], style={'width': '49%', 'display': 'inline-block'}),

        html.Div([
            dcc.Graph(id='facility-satisfaction-chart')
        ], style={'width': '49%', 'display': 'inline-block'})
    ])
])

# --- 6. Define Callbacks for Interactivity ---
@app.callback(
    [Output('summary-card', 'children'),
     Output('care-satisfaction-chart', 'figure'),
     Output('facility-satisfaction-chart', 'figure'),
     Output('facility-dropdown', 'value'), # Add output to reset dropdown
     Output('sex-dropdown', 'value')],      # Add output to reset dropdown
    [Input('facility-dropdown', 'value'),
     Input('sex-dropdown', 'value'),
     Input('reset-button', 'n_clicks')]
)
def update_dashboard(selected_facilities, selected_sexes, reset_clicks):
    triggered_id = ctx.triggered_id

    # --- Reset Logic ---
    if triggered_id == 'reset-button':
        selected_facilities = ['all']
        selected_sexes = ['all']
        filtered_df = df.copy()
    else:
        # --- Filtering Logic ---
        filtered_df = df.copy()
        if selected_facilities and 'all' not in selected_facilities:
            filtered_df = filtered_df[filtered_df['health_facility'].isin(selected_facilities)]
        if selected_sexes and 'all' not in selected_sexes:
            filtered_df = filtered_df[filtered_df['respondent_sex'].isin(selected_sexes)]

    if filtered_df.empty:
        summary_text = "No data matches the selected filters."
        empty_fig = {'layout': {'title': 'No data to display'}}
        reset_fac = ['all'] if triggered_id == 'reset-button' else selected_facilities
        reset_sex = ['all'] if triggered_id == 'reset-button' else selected_sexes
        return summary_text, empty_fig, empty_fig, reset_fac, reset_sex

    # --- Calculations for Summary ---
    num_respondents = len(filtered_df)
    avg_overall_satisfaction = filtered_df['overall_satisfaction_rating'].mean()
    # Determine max score dynamically from the mapping if possible, or assume 3
    max_score = 3 # Assuming 3 is the max score based on mapping
    try:
        numeric_overall = pd.to_numeric(df['overall_satisfaction_rating'], errors='coerce')
        if not numeric_overall.empty:
            max_score = numeric_overall.max()
    except Exception:
        pass # Keep default max_score if check fails

    summary_text = [
        html.Strong(f"Number of Respondents: "), f"{num_respondents}", html.Br(),
        html.Strong(f"Average Overall Satisfaction: "), f"{avg_overall_satisfaction:.2f} (out of {max_score or 'N/A'})"
    ]

    # --- Calculations for Charts ---
    care_means = filtered_df[care_satisfaction_cols].select_dtypes(include=np.number).mean().sort_values(ascending=False)
    facility_means = filtered_df[facility_satisfaction_cols].select_dtypes(include=np.number).mean().sort_values(ascending=False)

    # --- Create Figures ---
    if not care_means.empty:
        fig_care = px.bar(
            x=care_means.index,
            y=care_means.values,
            title="Average Care Satisfaction Scores",
            labels={'x': 'Aspect of Care', 'y': 'Average Score'},
            text_auto='.2f'
        )
        fig_care.update_layout(xaxis_tickangle=-45)
    else:
        fig_care = {'layout': {'title': 'No numeric care data to display'}}

    if not facility_means.empty:
        fig_facility = px.bar(
            x=facility_means.index,
            y=facility_means.values,
            title="Average Facility Satisfaction Scores",
            labels={'x': 'Facility Aspect', 'y': 'Average Score'},
            text_auto='.2f'
        )
        fig_facility.update_layout(xaxis_tickangle=-45)
    else:
        fig_facility = {'layout': {'title': 'No numeric facility data to display'}}

    reset_fac_val = ['all'] if triggered_id == 'reset-button' else selected_facilities
    reset_sex_val = ['all'] if triggered_id == 'reset-button' else selected_sexes

    return summary_text, fig_care, fig_facility, reset_fac_val, reset_sex_val

# --- 7. Run the App ---
if __name__ == '__main__':
    print("\nStarting Dash server...")
    print("Access the dashboard at: http://127.0.0.1:8050/")
    app.run_server(debug=True)
