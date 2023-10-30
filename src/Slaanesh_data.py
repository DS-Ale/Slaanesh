import pandas as pd
import datetime as dt
import Slaanesh_config as config
import Slaanesh_IGDB as igdb
import re
import requests

gl = pd.DataFrame()
pt = pd.DataFrame()


# todo: automatically create empty dataframes if none are found on startup
def create_empty_dataframes():
    return True


def load_dataframes():
    global gl, pt
    try:
        gl = pd.read_feather(config.game_list)
        pt = pd.read_feather(config.playthrough_list)
    except Exception as e:
        print(str(e))
        create_empty_dataframes()


# execute allows for temporarily turning off automatic writes, manually writing possible via UI
def write_dataframes(execute=True):
    if execute:
        global gl, pt
        gl.to_feather(config.game_list)
        pt.to_feather(config.playthrough_list)


def update_igdb_data(new_data):
    global gl
    for index, row in new_data.iterrows():
        gl_index = gl.index[gl['IGDB_ID'] == row['IGDB_ID']][0]
        save_cover(row['IGDB_image'], row['IGDB_ID'])
        gl.loc[[gl_index], ['IGDB_image']] = config.server_path_covers + str(row['IGDB_ID']) + '.png'
        gl.loc[[gl_index], ['Name']] = row['Name']
        gl.loc[[gl_index], ['IGDB_queried']] = row['IGDB_queried']
        gl.loc[[gl_index], ['Steam_ID']] = int(re.findall("\\d+", row['Steam_ID'])[0]) if type(row['Steam_ID']) is str else int(0)
        gl.loc[[gl_index], ['Release_date']] = row['Release_date'] if type(row['Release_date']) is int else int(0)
        gl.loc[[gl_index], ['IGDB_status']] = row['IGDB_status'] if type(row['IGDB_status']) is int else int(0)
        gl.loc[[gl_index], ['IGDB_url']] = row['IGDB_url']
    write_dataframes()


def save_cover(thumb: str, igdb_id: int):
    if not isinstance(thumb, str):
        return
    cover = 'https:' + thumb.replace("/t_thumb/", "/t_cover_big/")
    filename = config.path_covers + str(igdb_id) + '.png'
    try:
        with open(filename, 'xb') as f:
            res = requests.get(cover)
            f.write(res.content)
    except Exception as e:
        print(str(e))


def add_pt(igdb_id: int, date: dt.datetime, comment: str):
    global pt
    pt.reset_index(drop=True, inplace=True)
    pt.loc[len(pt.index)] = [int(igdb_id), date, comment]
    write_dataframes()


def edit_pt(index, date=None, comment=None):
    global pt
    if date is not None:
        pt.loc[index, 'Date'] = date
    if comment is not None:
        pt.loc[index, 'Playthrough_comment'] = comment
    write_dataframes()


def rem_pt(pt_index, gl_index):
    global pt
    igdb_id = pt.loc[pt_index, 'IGDB_ID']
    pt.drop(pt_index, axis=0, inplace=True)
    pt.reset_index(drop=True, inplace=True)
    if sum(pt['IGDB_ID'].eq(igdb_id)) == 0:
        global gl
        gl.loc[gl_index, 'Status'] = config.status_list_backlog[0]
    write_dataframes()


def add_game(name: str, igdb_id: int, platform: str, status: str, comment: str):
    global gl
    if igdb_id in gl['IGDB_ID']:
        return False
    pt.reset_index(drop=True, inplace=True)
    gl.loc[len(gl.index)] = ["", int(igdb_id), name, platform, status,
                             dt.datetime(1900, 1, 1, 1, 1, 1, 1), int(0), int(0), int(0), "", comment]
    igdb.update_id_queue.put(int(igdb_id))
    write_dataframes()


def edit_game(index, platform=None, status=None, comment=None):
    global gl
    if platform is not None:
        gl.loc[index, 'Platform'] = platform
    if status is not None:
        gl.loc[index, 'Status'] = status
    if comment is not None:
        gl.loc[index, 'Game_comment'] = comment
    write_dataframes()


def rem_game(index_gl, index_pt=None):
    global gl, pt
    if (index_pt is not None) and (not index_pt.empty):
        pt.drop(index_pt, axis=0, inplace=True)
        pt.reset_index(drop=True, inplace=True)
    gl.drop(index_gl, axis=0, inplace=True)
    gl.reset_index(drop=True, inplace=True)
    write_dataframes()


def check_consistency():
    global gl, pt
    # check ID data type
    if not gl['IGDB_ID'].dtype.kind in 'iu':
        raise Exception('Gamelist ID not valid')
    if not pt['IGDB_ID'].dtype.kind in 'iu':
        raise Exception('Playthroughs ID not valid')
    # check for duplicate IGDB IDs in game list
    if sum(gl['IGDB_ID'].duplicated()) > 0:
        raise Exception('Duplicate IGDB IDs in game list')
    # check whether all playthroughs have a date
    if sum(pt['Date'].isnull()) + sum(pt['Date'].isna()) + sum(pt['Date'] == "") > 0:
        raise Exception('Not all playthroughs have a date')
    res = pd.merge(pt, gl, how='left', on='IGDB_ID')
    # check whether all playthroughs have a game in gamelist
    if sum(res['Name'].isna()) > 0:
        raise Exception('Game missing for playthrough')
    # check whether all games with playthroughs have a played status
    if sum(res['Status'].isin(config.status_list_unplayed)) > 0:
        raise Exception('Game with playthrough has unplayed status')
    # check whether all games without playthoughs have an unplayed status
    tes = gl.drop(res.index, axis=0)
    if sum(tes['Status'].isin(config.status_list_played)) > 0:
        raise Exception('Game without playthrough has played status')
    # check whether all games have valid status
    if sum(~tes['Status'].isin(config.status_list_played + config.status_list_unplayed)) > 0:
        raise Exception('Game has invalid status')
    # check whether all games have valid platform
    if sum(~gl['Platform'].isin(config.platform_list)) > 0:
        raise Exception('Game has invalid platform')
