import chess
import chess.pgn
import chess.engine
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import requests
import json
import io
pd.set_option('display.max_rows', 15)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 300)

class PGNReader:
    engine_path = './engine/stockfish_14.1_win_x64_avx2.exe'
    eval_time = 15  # Set time for move evaluation
    limit = 60 # move limit for analysis
    df_cols = ['url', 'pgn', 'time_control', 'end_time', 'rated', 'time_class',
               'user_rating', 'user_username', 'user_result', 'user_color', 'opp_rating',
               'opp_username', 'opp_result', 'opp_color']

    df = pd.DataFrame(columns=df_cols)

    def __init__(self, username, lookback, time_control='300', limit=False):
        self.username = username
        self.lookback = lookback
        self.time_control = time_control
        self.get_games(self.username, self.lookback)
        self.filter_time_control(self.time_control)
        self.parse_player_stats()
        self.format_df()
        self.df_moves = self.get_move_scores()
        self.df = self.get_sample()
        self.df = pd.merge(self.df_moves, self.df, on='url', how='left')

    def get_games(self, username, lookback):
        """ Retrieve monthly game archive via Chess.com API"""
        dt = date.today()
        while lookback > 0:
            d = dt - relativedelta(months=lookback)
            d = d.strftime('%Y/%m')
            api_call = r'https://api.chess.com/pub/player/' + username + r'/games/2022/09'
            response = requests.get(api_call)
            j = json.loads(response.content.decode('utf-8'))
            print(j)
            self.df = self.df.append(pd.DataFrame(j['games']), sort=True)
            lookback -= 1

    def parse_player_stats(self):
        """ Parse the PGN JSON to assign white/black player to user/opponent """
        for index, row in self.df.iterrows():
            if self.df.iloc[index]['black']['username'] == self.username:
                user = 'black'
                opp = 'white'
            else:
                user = 'white'
                opp = 'black'

            self.df['user_rating'][index] = self.df.iloc[index][user]['rating']
            self.df['user_username'][index] = self.df.iloc[index][user]['username']
            self.df['user_result'][index] = self.df.iloc[index][user]['result']
            self.df['user_color'][index] = user
            self.df['opp_rating'][index] = self.df.iloc[index][opp]['rating']
            self.df['opp_username'][index] = self.df.iloc[index][opp]['username']
            self.df['opp_result'][index] = self.df.iloc[index][opp]['result']
            self.df['opp_color'][index] = opp

    def format_df(self):
        self.df.drop(columns=['black', 'white'], inplace=True)
        self.df['end_time'] = pd.to_datetime(self.df['end_time'], unit='s')

    def filter_time_control(self, time_control):
        self.df = self.df.loc[self.df['time_control'] == time_control]
        self.df.reset_index(drop=True, inplace=True)

    def get_sample(self):
        """ get a random single row from self.df"""
        df = self.df.sample()
        return df

    def get_move_scores(self):
        """ calculate the strength of each move made, compare to stength of best move"""
        self.df = self.df.sample()
        self.df = self.df.reset_index()
        url, fen, move_no, my_move_san, my_move_uci, my_move_score, best_move_san, best_move_uci, best_move_score, difs = [], [], [], [], [], [], [], [], [], []

        def get_move_score(board_info, color, mate=1500):
            if color == 'white':
                if board_info['score'].is_mate():
                    move_score = board_info['score'].white().score(mate_score=mate)
                else: 
                    move_score = int(format(board_info['score'].white().score()))
            else:
                if board_info['score'].is_mate():
                    move_score = board_info['score'].black().score(mate_score=mate)
                else: 
                    move_score = int(format(board_info['score'].black().score()))
            return move_score

        print('Number of games: ', self.df.shape[0])
        for index, row in self.df.iterrows():
            g = self.df.iloc[index]['pgn']
            print('analyzing game ', index + 1)

            user_color = self.df.iloc[index]['user_color']
            pgn = io.StringIO(g)
            game = chess.pgn.read_game(pgn)

            # setup board and engine
            board = chess.Board()
            engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            engine.configure({"Threads": 4})
            i = 0

            for move in game.mainline_moves():
                # Only analyse user moves
                if (i % 2 == 0 and user_color == 'black') or (i % 2 == 1 and user_color == 'white'):
                    board.push(move)
                    i += 1
                    continue

                # Get move, score and difference of user move and best move
                move_no.append(round((i+1)/2))
                mymove_info = engine.analyse(board, chess.engine.Limit(depth=self.eval_time))
                best_move_to_play = mymove_info['pv'][0]
                fen.append(str(board.fen()))
                san_move = board.san(move)
                board.push(move)
                mymove_info = engine.analyse(board, chess.engine.Limit(depth=self.eval_time))
                mymove_score = get_move_score(mymove_info, user_color)
                board.pop()
                san_best_move = board.san(best_move_to_play)
                board.push(best_move_to_play)
                bestmove_info = engine.analyse(board, chess.engine.Limit(depth=self.eval_time))
                bestmove_score = get_move_score(bestmove_info, user_color)
                dif = bestmove_score - mymove_score
                board.pop()
                board.push(move)

                # get fens, labels, povscores, difs
                url.append(self.df.iloc[index]['url'])
                my_move_san.append(san_move)
                my_move_uci.append(move)
                my_move_score.append(mymove_score)
                best_move_san.append(san_best_move)
                best_move_uci.append(best_move_to_play)
                best_move_score.append(bestmove_score)
                difs.append(dif)

                if i > self.limit:
                    break
                i += 1

            engine.quit()

        game_moves_df = pd.DataFrame(
            {'url': url,
             'fen': fen,
             'move_no': move_no,
             'my_move_san': my_move_san,
             'my_move_uci': my_move_uci,
             'my_move_score': my_move_score,
             'best_move_san': best_move_san,
             'best_move_uci': best_move_uci,
             'best_move_score': best_move_score,
             'difs': difs
             })

        return game_moves_df

pgn = PGNReader('markbouwman', 1, time_control='300')
df = pgn.df
df = df[['url','fen_x','move_no','my_move_uci','my_move_score','best_move_uci','best_move_score','difs']]
# df = df[df['difs'] > 100]
print(df)
content  = df.loc[0].to_json()
print(content)