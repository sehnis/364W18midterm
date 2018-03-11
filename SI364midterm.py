###############################
####### SETUP (OVERALL) #######
###############################

## Import statements
# Import statements
import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField # Note that you may need to import more here! Check out examples that do what you want to figure out what.
from wtforms.validators import Required, ValidationError # Here, too
from wtforms.widgets import TextArea
from flask_sqlalchemy import SQLAlchemy
import json
import requests


# Pybomb is an API Wrapper for the GiantBomb REST API.
import pybomb

## App setup code
app = Flask(__name__)
app.debug = True
app.use_reloader = True

## All app.config values
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///364midterm_sehnis.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

## Statements for db setup (and manager setup if using Manager)
db = SQLAlchemy(app)


######################################
######## HELPER FXNS (If any) ########
######################################

##################
##### MODELS #####
##################

class Username(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(64))
    userel = db.relationship('Review', backref='users')

    def __init__(self, namein):
        self.name = namein

    def __repr__(self):
        return "{} (ID: {})".format(self.name, self.id)

class Game(db.Model):
    __tablename__ = "games"
    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(128))
    tagline = db.Column(db.String(128))
    rating = db.Column(db.String(64))
    platforms = db.Column(db.String(256))
    gamerel = db.relationship('Review', backref='games')

    def __init__(self, dictin):
        self.name = dictin['name']
        self.tagline = dictin['tagline']
        self.rating = dictin['rating']
        self.platforms = dictin['platforms']

    def __repr__(self):
        return "{} (ID: {})".format(self.name, self.id)

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer,primary_key=True)
    game = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    reviewer = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    description = db.Column(db.String(512))
    tagrel = db.relationship('Tag', backref='reviews')

    def __init__(self, g, re, ra, d):
        self.game = g
        self.reviewer = re
        self.rating = ra
        self.description = d

    def __repr__(self):
        return "{} (ID: {})".format(self.game, self.id)

class Tag(db.Model):
    __tablename__ = "tags"
    id = db.Column(db.Integer,primary_key=True)
    review = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    tagtext = db.Column(db.String(64))

    def __init__(self, revin, textin):
        self.review = revin
        self.tagtext = textin

    def __repr__(self):
        return "{} (ID: {})".format(self.tagtext, self.id)

###################
###### FORMS ######
###################

class NameForm(FlaskForm):
    name = StringField("Please enter your name.",validators=[Required()])
    submit = SubmitField()

class GameForm(FlaskForm):
    name = StringField("Name of the Game: ",validators=[])
    platform = SelectField("Platform: ", choices=[('94', 'PC'), ('146', 'PlayStation 4'), ('17', 'Mac'), ('145', 'XBox One')], validators=[Required()])
    sorthow = SelectField("How to sort results: ", choices=[('name', 'By Name'), ('number_of_user_reviews', 'By Review Count'), ('date_last_updated', 'By Update Date')], validators=[Required()])
    submit = SubmitField()

class ReviewForm(FlaskForm):

    def score_validator(form, field):
        if int(field.data) > 10 :
            raise ValidationError('ERROR -- Your score cannot be higher than 10.')
        if int(field.data) < 1 :
            raise ValidationError('ERROR -- Your score cannot be lower than 1.')

    name = StringField("What is the full name of the Game?: ", validators=[Required()])
    reviewer = StringField("Who are you reviewing this game as?: ", validators=[Required()])
    score = StringField("Your Score out of 10: ", validators=[Required(), score_validator])
    desc = StringField("Please enter the text of your review: ", widget=TextArea())
    tags = StringField("Please enter any tags for your review, separated by commas: ")
    submit = SubmitField()


class TagForm(FlaskForm):
    tagtext = StringField("Select one or more tags to search (separated with commas): ")
    submit = SubmitField()

#######################
###### VIEW FXNS ######
#######################

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/', methods=['GET', 'POST'])
@app.route('/search', methods=['GET', 'POST'])
def search():
    form = GameForm()
    if form.validate_on_submit():

        my_key = '114d5ba3b41ef07a418ef17742dd0b7f2006f848'
        games_client = pybomb.GamesClient(my_key)
        response = games_client.search(
            filter_by={'name': form.name.data, 'platforms': form.platform.data},
            return_fields=('name', 'deck', 'original_game_rating', 'platforms'),
            sort_by=form.sorthow.data,
            desc=False,
            limit=25
        )

        found_games = []
        for indiv in response.results:
            result = {}
            result['name'] = indiv['name']
            result['tagline'] = indiv['deck']
            if indiv['original_game_rating']:
                result['rating'] = indiv['original_game_rating'][0]['name']
            else:
                result['rating'] = 'Unavailable'
            result['platforms'] = ''
            for p in indiv['platforms']:
                result['platforms'] += (p['name'] + " | ")
            found_games.append(result)

            new_game = Game(result)
            if not Game.query.filter_by(name=result['name']).first():
                db.session.add(new_game)
                db.session.commit()

        return render_template('game_results.html', results=found_games)
    return render_template('home.html',form=form)

@app.route('/new', methods=['GET', 'POST'])
def review():
    form = ReviewForm()
    if form.validate_on_submit():
        # Handling Username
        rev_name = form.reviewer.data
        found_user = Username.query.filter_by(name=rev_name).first()
        if found_user:
            rev_username = found_user.id
        else:
            new_user = Username(rev_name)
            db.session.add(new_user)
            db.session.commit()
            found_user = Username.query.filter_by(name=rev_name).first()
            rev_username = found_user.id
        # Handling the game name
        game_name = form.name.data
        found_game = Game.query.filter_by(name=game_name).first()
        if found_game:
            rev_game = found_game.id
        else:
            return render_template('new_review.html', form=form, errmess='ERROR -- Game not found. Make sure you have searched for it before.')
        # Adding the rating and description.
        rating = form.score.data
        if form.desc.data:
            rev_text = form.desc.data
        else:
            rev_text = 'No rationale given.'
        # Create the review; the tags are added after a review item is created.
        if Review.query.filter_by(reviewer=rev_username, game=rev_game).first():
            return render_template('new_review.html', form=form, errmess='ERROR -- This user has already submitted a review for this game.')
        new_review = Review(rev_game, rev_username, rating, rev_text)
        db.session.add(new_review)
        db.session.commit()
        # Handle the tags
        rev_tags = str(form.tags.data).split(",")
        found_review = Review.query.filter_by(reviewer=rev_username, game=rev_game).first()
        for rt in rev_tags:
            print(rt)
            if not Tag.query.filter_by(review=found_review.id, tagtext=rt.strip()).first():
                new_tag = Tag(found_review.id, rt.strip())
                db.session.add(new_tag)
                db.session.commit()
        return redirect(url_for('all_reviews'))
    return render_template('new_review.html',form=form)

@app.route('/tags', methods=['GET', 'POST'])
def tags():
    form = TagForm()
    return render_template('tags.html',form=form)

@app.route('/tag_results', methods=['GET', 'POST'])
def tag_results():
    results = []
    if request.args:
        tags = request.args.get('tagtext')
        tag_list = str(tags).split(",")
        for tl in tag_list:
            print('hit tl')
            found = Tag.query.filter_by(tagtext=tl.strip()).all()
            for f in found:
                print('hit f')
                rev = Review.query.filter_by(id=f.review).first()
                game = Game.query.filter_by(id=rev.game).first()
                user = Username.query.filter_by(id=rev.reviewer).first()
                rev_tuple = (user.name, game.name, rev.rating, tl)
                if rev_tuple not in results:
                    results.append(rev_tuple)
    return render_template('tag_results.html', tr=results)

@app.route('/results')
def show_games():
    return render_template('games_results.html')

@app.route('/names')
def all_names():
    names = Username.query.all()
    return render_template('name_example.html',names=names)

@app.route('/games')
def all_games():
    games = Game.query.all()
    return render_template('games_list.html',games=games)

@app.route('/reviews')
def all_reviews():
    revs = []
    for rev in Review.query.all():
        rev_game = Game.query.filter_by(id=rev.game).first().name
        rev_name = Username.query.filter_by(id=rev.reviewer).first().name
        revs.append((rev_name, rev_game, rev.rating, rev.description))
    return render_template('all_reviews.html',reviews=revs)




## Code to run the application...

# Put the code to do so here!
# NOTE: Make sure you include the code you need to initialize the database structure when you run the application!
if __name__ == '__main__':
    db.create_all()
    app.secret_key = 'somethingsecretthatillmakebetterlater'
    app.run(use_reloader=True,debug=True)