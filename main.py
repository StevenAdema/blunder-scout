import chess
import chess.pgn
import chess.engine
from chess.engine import Cp, Mate, MateGiven
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np
import io
import seaborn as sns
import requests
import ast
import json
import ast
from pgn_parser import pgn, parser
from flask import Flask, render_template      

def main():
    # KEY VARIABLES
    username = 'stevenadema'  # Chess.com username
    # enginepath = 'C:/Users/steven.adema/Downloads/stockfish-10-win/stockfish-10-win/Windows/stockfish_10_x64_bmi2.exe'
    enginepath = 'C:/Users/Steve/Downloads/stockfish-10-win/Windows/stockfish_10_x64_bmi2.exe'
    eval_time = 0.2  # Set time for move evaluation
    df_cols = ['url', 'pgn', 'time_control', 'end_time', 'rated', 'time_class', 'blitz']

    # df = pd.DataFrame(columns=df_cols)
    # df = get_games(username, 1, df)
    # df = df.head(20)

    with open('201909.json', 'r') as f:
        j = json.load(f)
    df = pd.DataFrame(j['games'])  
    df = df.head(10)

    # Save JSON
    # with open('201909.json', 'w') as f:
    #     json.dump(j, f)

    user_rating_arr = []
    user_username_arr = []
    user_result_arr = []
    user_color_arr = []
    opp_rating_arr = []
    opp_username_arr = []
    opp_result_arr = []
    opp_color_arr = []

    for index, row in df.iterrows():
        if df.iloc[index]['black']['username'] == username:
            user_rating_arr.append(df.iloc[index]['black']['rating'])
            user_username_arr.append(df.iloc[index]['black']['username'])
            user_result_arr.append(df.iloc[index]['black']['result'])
            user_color_arr.append("black")
            opp_rating_arr.append(df.iloc[index]['white']['rating'])
            opp_username_arr.append(df.iloc[index]['white']['username'])
            opp_result_arr.append(df.iloc[index]['white']['result'])
            opp_color_arr.append("white")
        else:
            user_rating_arr.append(df.iloc[index]['white']['rating'])
            user_username_arr.append(df.iloc[index]['white']['username'])
            user_result_arr.append(df.iloc[index]['white']['result'])
            user_color_arr.append("white")
            opp_rating_arr.append(df.iloc[index]['black']['rating'])
            opp_username_arr.append(df.iloc[index]['black']['username'])
            opp_result_arr.append(df.iloc[index]['black']['result'])
            opp_color_arr.append("black")

    df['user_rating'] = user_rating_arr
    df['user_username'] = user_username_arr
    df['user_result'] = user_result_arr
    df['user_color'] = user_color_arr
    df['opp_rating'] = opp_rating_arr
    df['opp_username'] = opp_username_arr
    df['opp_result'] = opp_result_arr
    df['opp_color'] = opp_color_arr

    df.drop(columns=['black', 'white'], inplace=True)
    df['end_time'] = pd.to_datetime(df['end_time'], unit='s')
    df = df.loc[df['time_control'] == '600']

    # df_users = get_opponent_info(df)
    # df = pd.concat([df, df_users], axis=1)

    # df = df.merge(df_users, how='inner', left_on='opp_username', right_on='username')
    # df.to_csv(r'C:\Users\Steve\Documents\GitHub\chess_analysis\code.csv', index=False, sep='|')

    game1 = df.iloc[5]['pgn']
    fen, mv, mv_score, bmv, bmv_score, difs = get_move_scores(df, username, enginepath, eval_time, game1)

    game1_df = pd.DataFrame(
        {'fen': fen,
         'mv': mv,
         'mv_score': mv_score,
         'bmv': bmv,
         'bmv_score': bmv_score,
         'difs': difs
        })
    print(game1_df)
    exit()

    mv_score = pd.Series.from_array(mv_score)
    # Plot the figure.
    plt.figure(figsize=(12, 8))
    ax = mv_score.plot(kind='bar')
    ax.set_xlabel('Move')
    ax.set_ylabel('Cp Score')
    ax.set_xticklabels(np.arange(len(labels)))

    rects = ax.patches

    for rect, label in zip(rects, labels):
        height = rect.get_height()
        ax.text(rect.get_x() + rect.get_width() / 2, height + 5, label,
            ha='center', va='bottom')

    plt.show()
    
    

def get_move_scores(df, username, enginepath, eval_time, g):
    user_color = df.iloc[5]['user_color']
    fen, mv, mv_score, bmv, bmv_score, difs = [], [], [], [], [], []

    pgn = io.StringIO(g)
    game = chess.pgn.read_game(pgn)

    # setup board and engine
    board = chess.Board()
    engine = chess.engine.SimpleEngine.popen_uci(enginepath)
    i = 0
    for move in game.mainline_moves():
        i += 1

        mymove_info = engine.analyse(board, chess.engine.Limit(time=eval_time))
        best_move = mymove_info['pv'][0]
        board.push(move)
        mymove_info = engine.analyse(board, chess.engine.Limit(time=eval_time))
        mymove_score = get_move_score(mymove_info, 'white')
        board.pop()
        board.push(best_move)
        bestmove_info = engine.analyse(board, chess.engine.Limit(time=eval_time))
        bestmove_score = get_move_score(bestmove_info, 'white')
        dif = bestmove_score - mymove_score
        print(mymove_score, ' ', bestmove_score)
        board.pop()
        board.push(move)

        # get fens, labels, povscores, difs
        fen.append(str(board.fen()))
        mv.append(str(move))
        mv_score.append(mymove_score)
        bmv.append(str(best_move))
        bmv_score.append(bestmove_score)
        difs.append(dif)

    engine.quit()
    return fen, mv, mv_score, bmv, bmv_score, difs

def get_move_score(board_info, color, mate=1000):
    if color == 'white':
        if board_info['score'].is_mate():
            m = board_info['score'].white().score(mate_score=mate)
        else: 
            m = int(format(board_info['score'].white().score()))
    elif color == 'black': 
        if board_info['score'].is_mate():
            m = board_info['score'].white().score(mate_score=mate)
        else: 
            m = int(format(board_info['score'].white().score()))
    else:
        print('Invalid color perspective chosen')

    return m        


if __name__ == "__main__":
    main()