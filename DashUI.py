import dash
from dash import dcc, html, ctx
from dash.dependencies import Input, Output, State
import json
import base64
from dash_selectable import DashSelectable
import io
from striprtf.striprtf import rtf_to_text
from datetime import date
"""
Functionality ideas:
- Could write "helper" functions for callbacks to increase readability of callbacks
-- Will become more necessary as other features are added (back, reverse relations, etc)
- Having the JSON be downloadable is nice and fine, but maybe it could be directly uploaded to git

Functionality to be added:
- Ability to read in files (besides RTF) and be added to sentences for data labeling (Look at: Dash upload component)
---- Ability to read metadata off of said files and assign them to a new dcc.Store so it can be added to every sentence's metadata
---- Instead, use dialog to prompt user for said metadata on file upload
- Ability to create opposite relations from a previous sentence *** Priority


Functionality to be updated:
- (Not Required) Being able to choose the file name for the download

Unexpected (or frustrating) Behavior:
- Clicking anywhere on the same "y" as the upload button opens the file menu
- After saving a json, the input sentences are removed and the program is basically reset
-- However, even though it is reset, you cannot upload the same file consecutively.
-- You CAN upload 1 paper, then upload a second paper, and they will combine in the storage.
--- This problem likely occurs based on how dash is handling uploads, and may not be fixable. 
--- Also, this issue may not be relevant as why would you upload the same thing multiple times consecutively.
--- This issue is probably due to the filename not changing within the app, thus not invoking the callback.
Errors in Functionality:
* As sentences currently do not reset until the json is saved, if you refresh the page, it will reset the sentence
* index, and return to 0.
** A potential solution to this is to add a skip sentence button, that will prevent adding the current sentence to the
** Storage.
"""

metadata_prompt = html.Div(hidden=True,children=[
    html.P(id="metadata-prompt-text",title="Please enter the following metadata."),
    html.Div([
        #"Title: ",
        dcc.Input(id='title', value='Title', type='text'),
        #"Author: ",
        dcc.Input(id='author', value='Author(s)', type='text'),
        dcc.Input(id='year', value='Year', type='text'),
    ]),
    html.Br(),
    html.Button("Finished",id='metadata-finish-button'),
])



app = dash.Dash(__name__)

app.layout = html.Div([
    html.Div([
        metadata_prompt,
        DashSelectable(
            id="dash-selectable",
            children=[html.P(id="sentence"), html.P(id="output")],
        ),
        html.Br(),
        html.Button('Source', id='source-btn', n_clicks=0),
        html.Button('Target', id='target-btn', n_clicks=0),
        html.Br(),
        html.Div(id='my-source'),

        html.Div(id='my-target'),

        html.Div(id='my-direction'),
        html.Br(),
        html.Br(),
        html.Button('Increase', id='increase-btn', n_clicks=0),
        html.Button('Decrease', id='decrease-btn', n_clicks=0),
        html.Button('Save Relation', id='save-btn', n_clicks=0),
        html.Button('Reset', id='reset-btn', n_clicks=0),
        html.Button('Back', id='back-btn', n_clicks=0),
        html.Button('Next', id='next-btn', n_clicks=0),
        html.Br(),
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                html.Button('Select Files')
        ]),),
        html.Button('Download JSON', id='download-btn', n_clicks=0),
        html.Br(),
        html.Div(id='stored-data'),
        html.Br(),
        html.Div(id="output-data-upload"),
        dcc.Store(id='input-sentences', data=["Please Insert RTF File"], storage_type='local'),

        dcc.Store(id='all-relation-store', data=[], storage_type='local'),
        # CHANGE BACK TO SESSION OR LOCAL FOR RESEARCHER RELEASE

        dcc.Store(id='current-relation-store',data={"src":"","tgt":"","direction":""},storage_type='memory'),
        dcc.Store(id='meta-data',data={"title": "", "authors": "", "year": ""},storage_type='memory'),
        dcc.Download(id="download-json"),
    ])
])


@app.callback(Output("output", "children"),
              [Input("dash-selectable", "selectedValue")])
def display_output(value):
    text = ""
    if value:
        text = value

    return "Currently selected: {}".format(text)


@app.callback(
    [Output('all-relation-store', 'data',allow_duplicate=True),
     Output('sentence','children'),
     Output('current-relation-store', 'data',allow_duplicate=True),
     Output('next-btn', 'n_clicks',allow_duplicate=True),
     Output('back-btn', 'n_clicks',allow_duplicate=True)],
    [Input('next-btn', 'n_clicks'),
     Input('back-btn', 'n_clicks')],
    [State('sentence', 'children'),
     State('all-relation-store', 'data'),
     State('current-relation-store', 'data'),
     State('input-sentences','data'),],
    prevent_initial_call='initial_duplicate',
)
def next_sentence(n_clicks, back_clicks, current_text, all_data,curr_relation,sentences):
    current_sentence_index = int(n_clicks) - int(back_clicks)
    button_id = ctx.triggered_id if not None else False
    if len(sentences) == 1:  # Prevents moving the amount of clicks, and thus the index of sentences
        # , when there is no file [On start, and after download]
        return all_data, sentences[0], curr_relation, 0, 0
    if current_sentence_index < 0: #if we've gone negative, we can just reset the clicks and return default sentence
        return all_data, sentences[0], curr_relation, 0, 0
    if current_sentence_index == 0:
        return all_data, sentences[current_sentence_index], curr_relation, 0, 0
    elif current_sentence_index == 1:
        return all_data, sentences[current_sentence_index], curr_relation, n_clicks, back_clicks
    elif current_sentence_index < len(sentences):
        # Handling case where current relation is not filled out enough to be usable
        if button_id == "back-btn":
            index = current_sentence_index
        else:
            index = current_sentence_index - 2 # -1 because of starter sentence,-1 again because next button makes index + 1
            # of where we are saving, so -2
        all_data = saving_relation(index,all_data,curr_relation)
        curr_relation = {'src':"",'tgt':'','direction':''}
        return all_data, sentences[current_sentence_index], curr_relation, n_clicks, back_clicks
    elif all_data[-1]["text"] == current_text:
        # This case is hit when the user hits the final sentence of a paper, and hits next 1 additional time
        # This makes sure that the last sentence is saved.
        # The following code in this elif could be made into a function as it is now repeated.
        all_data = saving_relation(-1,all_data,curr_relation)
        curr_relation = {'src': "", 'tgt': '', 'direction': ''}
        if button_id == "back_btn":
            return all_data, sentences[-2], curr_relation, n_clicks, back_clicks
        else:
            return all_data, sentences[-1], curr_relation, n_clicks-1, back_clicks
    else:
        return all_data, current_text, curr_relation, n_clicks, back_clicks

# Callback for increase, decrease, source,target, save, and reset in the following


@app.callback(
    [Output('my-direction','children'),
     Output('my-source','children'),
     Output('my-target','children'),
     Output("current-relation-store", "data")],
    [Input('increase-btn', 'n_clicks'),
     Input('decrease-btn', 'n_clicks'),
     Input('source-btn', 'n_clicks'),
     Input('target-btn', 'n_clicks'),
     Input('next-btn', 'n_clicks'),
     Input('reset-btn', 'n_clicks')],
    [State("dash-selectable", "selectedValue"),
     State("current-relation-store", "data")],
)
def allLabel(inc,dec,src,tgt,next,reset,selected_data,relation):
    """
    Function that handles all relation button data
    :param inc: Increase button
    :param dec: Decrease button
    :param src: Source button
    :param tgt: Target button
    :param next: Next button - allows next button to access function
    :param reset: Reset button - allows reset button to access function
    :param selected_data: User-selected data
    :param relation: Relation data storage
    :return: [Direction text, ]
    """
    button_id = ctx.triggered_id if not None else False
    direcText = f"Direction: "
    srcText = f"Source: "
    tgtText = f"Target: "
    if button_id == "increase-btn":
        relation["direction"] = "Increase"
        return f"Direction: Increase",dash.no_update, dash.no_update,relation
    elif button_id == "decrease-btn":
        relation["direction"] = "Decrease"
        return f"Direction: Decrease",dash.no_update, dash.no_update,relation
    elif button_id == "source-btn":
        relation["src"] = selected_data
        return dash.no_update, f"Source: {selected_data}", dash.no_update,relation
    elif button_id == "target-btn":
        relation["tgt"] = selected_data
        return dash.no_update, dash.no_update, f"Target: {selected_data}",relation
    elif button_id == "reset-btn":
        relation = {'src': "", 'tgt': '', 'direction': ''}
        return direcText, srcText, tgtText, relation
    else: # This else corresponds to initial call (program start) and when the next button is hit
        # Have not tried multiple changes to one output from one button,
        # and it probably isn't a good idea, so don't change this
        return direcText,srcText,tgtText,relation


@app.callback(
    [Output('all-relation-store','data',allow_duplicate=True),
     Output('current-relation-store','data',allow_duplicate=True)],
    [Input('save-btn', 'n_clicks')],
    [State('current-relation-store','data'),
     State('all-relation-store', 'data'),
     State('next-btn', 'n_clicks'),
     State('back-btn', 'n_clicks')],
    prevent_initial_call=True,
)
def save_relation(n_clicks,curr_relation,all_data,for_index,back_index):
    index = int(for_index)-int(back_index)
    if index <= 0:
        return all_data,dash.no_update
    all_data = saving_relation(index-1,all_data,curr_relation)
    return all_data,dash.no_update

def saving_relation(index,all_data,curr_relation):
    if curr_relation["src"] == '' or curr_relation["tgt"] == '':
        pass
    else:
        if len(all_data[index]["causal relations"]):
            check = False
            for relation in all_data[index]["causal relations"]:
                if relation == curr_relation:
                    check = True
            if not check:  # checking if its a duplicate
                all_data[index]["causal relations"].append(curr_relation)
        else:
            all_data[index]["causal relations"].append(curr_relation)
    return all_data

@app.callback(
    Output('stored-data','children'),
    Input('all-relation-store','data'),
)
def currentStorage(data):
    if not data:
        return f"Stored: []"
    return f"Stored: {data}"


@app.callback(
    [Output("download-json", "data"),
     Output('all-relation-store','data'),
     Output('input-sentences','data', allow_duplicate=True),
     Output('next-btn','n_clicks'),
     ],
    Input("download-btn", "n_clicks"),
    [State('all-relation-store','data'),
     State('next-btn','n_clicks'),
     State('input-sentences','data'),
     State('upload-data', 'filename')],
    prevent_initial_call=True,
)
def download(n_clicks,data,curr_sen_index, inp_sentences,file):
    # In current implementation, only required variables are the input (download-btn)
    # and the state of all-relation-store
    """

    :param n_clicks:
    :param data:
    :param curr_sen_index:
    :param inp_sentences:
    :return: json, relational storage, input_sentences, next btn n_clicks
    """
    # WHEN YOU HIT SAVE, YOU ARE DONE WITH THAT SESSION, ALL REMAINING SENTENCES ARE REMOVED, AND THE PROGRAM IS
    # BASICALLY RESET
    if not data:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    fileData = json.dumps(data, indent=2)
    today = date.today()
    if file is None:
        return dict(content=fileData, filename=f"Labeled_Data-{today}.json"), [], ["Please Insert RTF File"], 0
    file = file.replace(".rtf",f"-{today}.json")
    return dict(content=fileData, filename=file), [], ["Please Insert RTF File"], 0


# This callback also activates on download, and updates the text on screen.


@app.callback(
    Output('output-data-upload', 'children', allow_duplicate=True),
    Input('input-sentences','data'),
    prevent_initial_call='initial_duplicate',
)
def refresh(inp_sentences):
    return f"Current Sentences: {inp_sentences}" + f" Length: {len(inp_sentences)}"


def abbreviation_handler(sentences):
    # File handler helper function
    sentences_to_add = []
    temp = sentences[0]
    for i in range(len(sentences) - 1):
        if sentences[i] == '':
            continue
        if not (sentences[i + 1].strip())[0].isupper():
            temp = temp + '. ' + sentences[i + 1]
        else:
            sentences_to_add.append(temp)
            temp = sentences[i + 1]
    sentences_to_add.append(temp)
    return sentences_to_add


@app.callback([Output('input-sentences','data'),
               Output('all-relation-store','data', allow_duplicate=True),
               Output(metadata_prompt,'hidden')],
              Input('upload-data', 'contents'),
              [State('upload-data', 'filename'),
               State('input-sentences','data'),
               State('all-relation-store','data')],
            prevent_initial_call="initial_duplicate"
)
def update_output(list_of_contents, list_of_names,inp_sentences,data):
    if list_of_contents is None:
        if len(inp_sentences) > 1:
            return inp_sentences, dash.no_update, dash.no_update
        return dash.no_update, dash.no_update, dash.no_update
    content_type, content_string = list_of_contents.split(',')
    decoded = base64.b64decode(content_string)
    if ".rtf" in list_of_names:
        temp = io.StringIO(decoded.decode('utf-8')).getvalue()
        text = rtf_to_text(temp)
        period_split = text.split(". ")
        sentences = []
        for sentence in period_split:
            temp = sentence.split(".\n")
            if type(temp) is str:
                sentences.append(sentence)
            else:
                for sen in temp:
                    if sen == "":
                        continue
                    sentences.append(sen)
        sentences = abbreviation_handler(sentences)
        for sentence in sentences:
            if sentence == '':
                continue
            sentence = sentence.replace("\n", "")
            sentence = sentence + "."
            inp_sentences.append(sentence)
            template = {"text": sentence,
                        "causal relations": [],
                        "meta_data": {"title": "", "authors": "", "year": ""}}
            data.append(template)

    return inp_sentences, data, False

@app.callback([Output(metadata_prompt,'hidden',allow_duplicate=True),
               Output('all-relation-store','data', allow_duplicate=True)],
              Input('metadata-finish-button', 'n_clicks'),
              [State('title', 'value'),
               State('author','value'),
               State('year','value'),
               State('all-relation-store','data'),],
            prevent_initial_call="initial_duplicate"
)

def metadata(n_clicks, title, author, year, data):
    meta_dict = {"title": title, "authors": author, "year": year}
    for i in range(len(data)):
        if data[i]["meta_data"] == {"title": "", "authors": "", "year": ""}:
            data[i]["meta_data"] = meta_dict
    return True, data

if __name__ == '__main__':
    app.run_server(debug=True)