import json
import os
import random
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from bokeh.embed import components
from bokeh.models import (ColumnDataSource, HoverTool, LabelSet, Legend,
                          LegendItem)
from bokeh.palettes import Viridis5
from bokeh.plotting import figure
from bson.objectid import ObjectId
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_wtf import FlaskForm
from pymongo import MongoClient
from wtforms import SelectField

client = MongoClient(
    "Contact repo manager for DB access")

app = Flask(__name__)
app.secret_key = os.urandom(24)


class CountryForm(FlaskForm):
    continent = SelectField('continent', choices=[
                            'Africa', 'Asia', 'Europe', 'North America', 'South America', 'Oceania'])
    country = SelectField('country', choices=[])


class DateForm(FlaskForm):
    date = SelectField('date', choices=[])


@app.route('/', methods=['GET', 'POST'])
def main():
    db = client['covid19']
    collection = db['Africa']

    # Set default dropdown choices with Africa
    countries_list = []
    for country in collection.find({"continent": "Africa"}, {"location": 1}):
        country_id = country.get("_id")
        country_name = country.get("location")
        country_pair = (country_id, country_name)
        countries_list.append(country_pair)

    # Set up continent/country form
    country_form = CountryForm()
    country_form.country.choices = countries_list

    # Set dropdown choices for days
    time_list = []
    start_date = date(2020, 1, 1)
    end_date = date(2020, 11, 1)
    delta = timedelta(days=1)
    while start_date <= end_date:
        time_list.append(start_date.strftime("%Y-%m-%d"))
        start_date += delta

    # Set up date form
    date_form = DateForm()
    date_form.date.choices = time_list

    # Headers, data and HTML components for tables/graphs to be rendered on webpage
    summary_headers, summary_data = (), ()
    country_headers, country_data, world_rank_data = (), (), ()
    document_list = []
    covid_headers, covid_data = (), ()
    stringency_script, stringency_div = "", ""
    case_script, case_div = "", ""
    death_script, death_div = "", ""
    age_chart_script, age_chart_div = "", ""
    hdi_chart_script, hdi_chart_div = "", ""

    if request.method == "POST":
        continent = country_form.continent.data
        collection = db[f"{continent}"]
        for document in collection.find({"_id": ObjectId(country_form.country.data)}, {"_id": 0, "location": 1}):
            country = document.get("location")

        # Queries to get summary aggregated statistics
        summary_cases = ('{:,}'.format(
            summary_query(str(datetime.strptime(date_form.date.data, '%Y-%m-%d').date()), "total_cases")))
        summary_deaths = ('{:,}'.format(
            summary_query(str(datetime.strptime(date_form.date.data, '%Y-%m-%d').date()), "total_deaths")))

        # Consolidate above queries into tuple to render on the webpage
        summary_headers = ("TOTAL CASES", "TOTAL DEATHS")
        summary_data = (summary_cases, summary_deaths)

        # Queries to get country statistics
        population = ('{:,}'.format(cursor_stats(continent, ObjectId(
            country_form.country.data), "population"))) if cursor_stats(continent, ObjectId(
                country_form.country.data), "population") > 1000 else cursor_stats(continent, ObjectId(
                    country_form.country.data), "population")
        med_age = cursor_stats(continent, ObjectId(
            country_form.country.data), "median_age")
        percent_pop_65 = cursor_stats(continent, ObjectId(
            country_form.country.data), "aged_65_older")
        gdp = ('{:,}'.format(cursor_stats(continent, ObjectId(
            country_form.country.data), "gdp_per_capita"))) if cursor_stats(continent, ObjectId(
                country_form.country.data), "gdp_per_capita") > 1000 else cursor_stats(continent, ObjectId(
                    country_form.country.data), "gdp_per_capita")
        hospital_beds = cursor_stats(continent, ObjectId(
            country_form.country.data), "hospital_beds_per_thousand")
        life_expectancy = cursor_stats(continent, ObjectId(
            country_form.country.data), "life_expectancy")
        human_dev_index = cursor_stats(continent, ObjectId(
            country_form.country.data), "human_development_index")

        # Consolidate above queries into tuple to render on the webpage
        country_headers = ("Population", "Median Age", "Percent of Population 65+", "Per Capita GDP",
                           "Hospital Beds Per Thousand", "Life Expectancy", "Human Development Index")
        country_data = (population, med_age, percent_pop_65, gdp,
                        hospital_beds, life_expectancy, human_dev_index)

        # Queries to get world ranking of country for various statistics
        collections_list = ['Africa', 'Asia', 'Europe',
                            'North America', 'South America', 'Oceania']
        # Create list of every country in the world with field
        for collection in collections_list:
            collection = db[collection]
            for document in collection.find({}, {"location": 1, "population": 1, "median_age": 1, "aged_65_older": 1, "gdp_per_capita": 1, "hospital_beds_per_thousand": 1, "life_expectancy": 1, "human_development_index": 1}):
                document_list.append(document)

        population_rank = cursor_rank(ObjectId(
            country_form.country.data), document_list, "population")
        med_age_rank = cursor_rank(ObjectId(
            country_form.country.data), document_list, "median_age")
        percent_pop_65_rank = cursor_rank(ObjectId(
            country_form.country.data), document_list, "aged_65_older")
        gdp_rank = cursor_rank(ObjectId(
            country_form.country.data), document_list, "gdp_per_capita")
        hospital_beds_rank = cursor_rank(ObjectId(
            country_form.country.data), document_list, "hospital_beds_per_thousand")
        life_expectancy_rank = cursor_rank(ObjectId(
            country_form.country.data), document_list, "life_expectancy")
        human_dev_index_rank = cursor_rank(ObjectId(
            country_form.country.data), document_list, "human_development_index")

        # Consolidate above queries into tuple to render on the webpage
        world_rank_data = (population_rank, med_age_rank, percent_pop_65_rank,
                           gdp_rank, hospital_beds_rank, life_expectancy_rank, human_dev_index_rank)

        # Queries to get covid statistics
        new_cases = ('{:,}'.format(cursor_covid(continent, ObjectId(
            country_form.country.data), date_form.date.data, "new_cases"))) if cursor_covid(continent, ObjectId(
                country_form.country.data), date_form.date.data, "new_cases") > 1000 else cursor_covid(continent, ObjectId(
                    country_form.country.data), date_form.date.data, "new_cases")
        new_deaths = ('{:,}'.format(cursor_covid(continent, ObjectId(
            country_form.country.data), date_form.date.data, "new_deaths"))) if cursor_covid(continent, ObjectId(
                country_form.country.data), date_form.date.data, "new_deaths") > 1000 else cursor_covid(continent, ObjectId(
                    country_form.country.data), date_form.date.data, "new_deaths")
        tot_cases = ('{:,}'.format(cursor_covid(continent, ObjectId(
            country_form.country.data), date_form.date.data, "total_cases"))) if cursor_covid(continent, ObjectId(
                country_form.country.data), date_form.date.data, "total_cases") > 1000 else cursor_covid(continent, ObjectId(
                    country_form.country.data), date_form.date.data, "total_cases")
        tot_deaths = ('{:,}'.format(cursor_covid(continent, ObjectId(
            country_form.country.data), date_form.date.data, "total_deaths"))) if cursor_covid(continent, ObjectId(
                country_form.country.data), date_form.date.data, "total_deaths") > 1000 else cursor_covid(continent, ObjectId(
                    country_form.country.data), date_form.date.data, "total_deaths")
        case_growth_rate_DoD = cursor_covid_case_growth(continent, ObjectId(
            country_form.country.data), date_form.date.data,
            str(datetime.strptime(date_form.date.data, '%Y-%m-%d').date() - timedelta(days=1)))

        # Consolidate above queries into tuple to render on the webpage
        covid_headers = ("New Cases", "New Deaths",
                         "Total Cases", "Total Deaths", "Percent case growth rate day-over-day")
        covid_data = (new_cases, new_deaths, tot_cases,
                      tot_deaths, case_growth_rate_DoD)

        # Create HTML components for bokeh visualizations to send to frontend
        stringency_script, stringency_div = make_line_plot(
            continent, ObjectId(country_form.country.data), "stringency_index")
        case_script, case_div = make_line_plot(
            continent, ObjectId(country_form.country.data), "new_cases")
        death_script, death_div = make_line_plot(
            continent, ObjectId(country_form.country.data), "new_deaths")
        age_chart_script, age_chart_div = make_line_compares(
            ObjectId(country_form.country.data), country, "aged_65_older", "new_cases")
        hdi_chart_script, hdi_chart_div = make_line_compares(
            ObjectId(country_form.country.data), country, "human_development_index", "new_cases")

    return render_template('main.html',
                           country_form=country_form,
                           date_form=date_form,
                           summary_headers=summary_headers,
                           summary_data=summary_data,
                           country_headers=country_headers,
                           country_data=country_data,
                           world_rank_data=world_rank_data,
                           covid_headers=covid_headers,
                           covid_data=covid_data,
                           stringency_script=stringency_script,
                           stringency_div=stringency_div,
                           case_script=case_script,
                           case_div=case_div,
                           death_script=death_script,
                           death_div=death_div,
                           age_chart_script=age_chart_script,
                           age_chart_div=age_chart_div,
                           hdi_chart_script=hdi_chart_script,
                           hdi_chart_div=hdi_chart_div,
                           country=country
                           )


# Helper function for quick summary aggregation queries
def summary_query(date, field):
    db = client['covid19']
    collections_list = ['Africa', 'Asia', 'Europe',
                        'North America', 'South America', 'Oceania']
    sum = 0

    # Find total cases or deaths from beginning of the Pandemic to a certain date
    for collection in collections_list:
        collection = db[collection]
        for document in collection.find({"data.date": date}, {"data.date": 1, f"data.{field}": 1}):
            for dict in document.get("data"):
                if dict.keys() >= {"date", field} and dict.get("date") == date:
                    sum += dict.get(field)

    return sum


# Helper function for quick country statistic queries
def cursor_stats(continent, country_id, field_stat):
    db = client['covid19']
    collection = db[f"{continent}"]

    country_stat = 0
    document = list(collection.find(
        {"_id": country_id}, {"_id": 0, field_stat: 1}))

    # If the statistic is unavailable, return "Not Available"
    for dict in document:
        if bool(dict) == False:
            return country_stat
        country_stat = dict.get(field_stat)

    return country_stat


# Helper function for country ranking in the world by a statistical measure
def cursor_rank(country_id, doc_list, field_covid):
    # Sort the document/country list based on the field
    new_document_list = []
    for dict in doc_list:
        if field_covid in dict:
            new_document_list.append(dict)
    document_list_sorted = sorted(
        new_document_list, key=lambda i: i[field_covid], reverse=True)
    country_rank = "Not Available"

    # Based on the field, find selected country's ranking for the given statistic
    rank = 1
    for dict in document_list_sorted:
        if field_covid not in dict:
            return country_rank
        if dict.get("_id") == country_id:
            country_data = dict
            break
        rank += 1

    return rank


# Helper function for quick covid statistic queries
def cursor_covid(continent, country_id, date, field):
    db = client['covid19']
    collection = db[f"{continent}"]

    # Find list of dicts containing date and {field_covid} for choice country
    covid_stat = 0
    for document in collection.find({"_id": country_id}, {"_id": 0, "data.date": 1, f"data.{field}": 1}):
        covid = document.get("data")

    # Loop through dicts until finding the one with the corresponding date from dropdown
    for dict in covid:
        if dict.get("date") == date:
            covid_stat = dict
            break
    if covid_stat == 0 or covid_stat.get(field) is None:
        return 0

    return covid_stat.get(field)


# Helper function for quick covid statistic queries
def cursor_covid_case_growth(continent, country_id, date_today, date_yesterday):
    db = client['covid19']
    collection = db[f"{continent}"]
    covid_case_growth = 0

    # If the date is the first date of the year (i.e. no previous date exists in data)
    if date_today == '2020-01-01':
        return 0

    # Find list of dicts containing date and total cases for choice country
    for document in collection.find({"_id": country_id}, {"_id": 0, "data.date": 1, "data.total_cases": 1}):
        covid = document.get("data")

    # Loop through dicts until finding the ones corresponding with the dropdown choice date and one day earlier date
    case_today, case_yesterday = {}, {}
    for dict in covid:
        if dict.get("date") == date_yesterday:
            case_yesterday = dict
            if "total_cases" not in case_yesterday:
                return 0
        if dict.get("date") == date_today:
            case_today = dict
            if "total_cases" not in case_today:
                return 0
            break

    if bool(case_today) == False or bool(case_yesterday) == False:
        return covid_case_growth

    # Calculate case growth rate over previous day
    case_growth = (case_today.get("total_cases") -
                   case_yesterday.get("total_cases"))/(case_yesterday.get("total_cases"))*100

    return round(case_growth, 2)


# Helper function to make plot HTML components for stringency index, total cases, and total deaths line plots
def make_line_plot(continent, country_id, field):
    db = client['covid19']
    collection = db[f"{continent}"]

    # Find list of dicts containing date, total_cases, and total_deaths for choice country
    for document in collection.find({"_id": country_id}, {"_id": 0, "data.date": 1, f"data.{field}": 1}):
        plot_data = list(document.get("data"))

    # Set total_cases and total_deaths to 0 for days where no data exists
    for dict in plot_data:
        if field not in dict:
            dict[field] = 0

    # Create lists for x and y coordinates
    x = pd.to_datetime([dict['date'] for dict in plot_data])
    y = [dict[field] for dict in plot_data]
    data = {'x_values': x,
            'y_values': y}
    source = ColumnDataSource(data=data)

    # Create line plot with HTML components to send to frontend
    field_list = ["new_cases", "new_deaths", "stringency_index"]
    title_list = ["Daily Cases",
                  "Daily Deaths", "Daily Stringency Index"]
    color_list = ["red", "green", "yellow"]
    index = 0
    plot = figure(plot_height=300, sizing_mode='scale_width',
                  x_axis_type="datetime")
    plot.line(x='x_values', y='y_values', source=source, line_width=3)
    for stat in field_list:
        if stat == field:
            plot.title.text = title_list[index]
            plot.add_tools(HoverTool(
                tooltips=[("Date", "$x{%F}"),
                          (title_list[index], "$y")],
                formatters={"$x": 'datetime'}, mode='vline'))
            break
        index += 1
    script, div = components(plot)

    return script, div


# Helper function to make plot HTML components for country comparison plots based on Pop% > 65 and HDI
def make_line_compares(country_id, country_name, field_compare, field_display):
    db = client['covid19']
    collections_list = ['Africa', 'Asia', 'Europe',
                        'North America', 'South America', 'Oceania']
    document_list, countries_comparison = [], []
    country_data = {}
    script, div = "", ""

    # Create list of every country in the world with field
    for collection in collections_list:
        collection = db[collection]
        for document in collection.find({}, {"location": 1, field_compare: 1, "data.date": 1, f"data.{field_display}": 1}):
            if field_compare in document:
                document_list.append({"_id": document.get("_id"), "location": document.get(
                    "location"), field_compare: document.get(field_compare), "data": document.get("data")})

    # Sort the country list based on the field
    document_list_sorted = sorted(
        document_list, key=lambda i: i[field_compare])

    # Based on the field, find countries +/- 2 spots from the selected country in the sorted list
    index = 0
    trigger = False
    for dict in document_list_sorted:
        if dict.get("_id") == country_id:
            country_data = dict
            trigger = True
            break
        index += 1

    # Return empty HTML components (i.e. not render chart) if the field does not exist for the selected country
    if trigger == False:
        return script, div

    # Find four other countries to compare the selected country to
    # Handle cases of countries in lowest end of list
    placemarker = index
    remaining_list_size = 5
    if index in range(0, 2):
        while index >= 0:
            countries_comparison.append(document_list_sorted[index])
            index -= 1
        remaining_list_size -= len(countries_comparison)
        while remaining_list_size > 0:
            countries_comparison.append(document_list_sorted[placemarker + 1])
            placemarker += 1
            remaining_list_size -= 1

    # Handle cases of countries in highest end of list
    elif index in range(len(document_list_sorted) - 2, len(document_list_sorted)):
        while index < len(document_list_sorted):
            countries_comparison.append(document_list_sorted[index])
            index += 1
        remaining_list_size -= len(countries_comparison)
        while remaining_list_size > 0:
            countries_comparison.append(document_list_sorted[placemarker - 1])
            placemarker -= 1
            remaining_list_size -= 1

    # Handles any other case
    else:
        countries_comparison = [document_list_sorted[index - 2], document_list_sorted[index - 1],
                                country_data, document_list_sorted[index + 1], document_list_sorted[index + 2]]
    countries_comparison_sorted = sorted(
        countries_comparison, key=lambda i: i[field_compare])

    # Create lists to store plot data
    data_list, country_list, time_list, case_list = [], [], [], []
    for dict in countries_comparison_sorted:
        country_list.append(dict.get("location"))
        data_list.append(dict.get("data"))

    # Organizes data_list into two lists of lists, one for dates and the other for new_cases
    country_marker = 0
    for list in data_list:
        time_temp, case_temp = [], []
        for dict in list:
            if "new_cases" in dict:
                time_temp.append(dict.get("date"))
                case_temp.append(dict.get("new_cases"))
        if len(case_temp) > 0:
            time_list.append(pd.to_datetime(time_temp))
            case_list.append(case_temp)
        else:
            # Removes the country from country_list if there is no data on it
            del country_list[country_marker]
        country_marker += 1

    # Create line plot with HTML components to send to frontend
    title = f"Daily cases for countries close to {country_name} in terms of Percent of population older than 65" if field_compare == "aged_65_older" else f"Daily cases for countries close to {country_name} in terms of Human Development Index"
    plot = figure(plot_height=300, x_axis_type="datetime",
                  sizing_mode='scale_width', title=title)
    r = plot.multi_line(xs=time_list, ys=case_list, line_color=random.sample(
        Viridis5, len(case_list)), line_width=3)
    legend_list = []
    index = 0
    # Create legend
    for country in country_list:
        legend_list.append(LegendItem(
            label=country, renderers=[r], index=index))
        index += 1
    legend = Legend(items=legend_list)
    plot.add_layout(legend)
    plot.legend.location = 'top_left'
    script, div = components(plot)

    return script, div


@app.route('/country/<continent>')
def country(continent):
    db = client['covid19']
    collection = db[f"{continent}"]
    countries_array = []

    # Find matching countries for continent with country id and country name
    for country in collection.find({"continent": f"{continent}"}, {"location": 1}):
        country_obj = {}
        country_obj['id'] = str(country.get("_id"))
        country_obj['name'] = country.get("location")
        countries_array.append(country_obj)

    return jsonify({'countries': countries_array})


if __name__ == '__main__':
    app.run(debug=True)
