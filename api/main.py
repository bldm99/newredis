#!/usr/bin/env python

import os
import json
import redis
from flask import Flask, request, jsonify
from flask_cors import CORS , cross_origin
import pandas as pd
from linkextractor import columnas
import numpy as np
from scipy.spatial.distance import cityblock


app = Flask(__name__)
CORS(app)

redis_conn = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

@app.route("/")
def index():
    return "Usage: http://<hostname>[:<prt>]/api/<url>"

#----------------------------------------------------------------
total = {}
valoresfinal = {}
peliculasp = {}
df = pd.DataFrame()
csv_path = '/shared_data/movie.csv'

@app.route('/api/csv', methods=['POST'])
def recibir_csv():
    global df
    if request.method == 'POST':
        data = request.get_json()  
        nombre = data.get('obj')  
        df = pd.DataFrame(nombre)
        csv_path = '/shared_data/movie.csv'
        df.to_csv(csv_path, index=False)
        redis_conn.set('csv', json.dumps(nombre))
        return jsonify({"csv cargado correctamente a redis"})
    else:
        return jsonify({"mensaje": "Esta ruta solo acepta solicitudes POST"})


@app.route('/api/valor', methods=['POST'])
def recibir_datos():
    global valoresfinal , peliculasp
    if request.method == 'POST':
        data = request.get_json()  

        col1 = data.get('col1')
        col2 = data.get('col2')
        col3 = data.get('col3')

        numero = data.get('numero')  
        numerox = int(numero)
        csv_path = '/shared_data/movie.csv'
        af = pd.read_csv(csv_path)
        
        peli = af

        peli[col3] = pd.to_numeric(peli[col3], errors='coerce')
        #peli['movieId'] = pd.to_numeric(peli['movieId'], errors='coerce')
        peli[col1] = pd.to_numeric(peli[col1], errors='coerce')


        consolidated_dfmi = columnas(peli, col1, col2, col3)
        #consolidated_dfmi = consolidated_dfmi.head(300)
        #consolidated_dfmi = pd.concat([consolidated_dfmi.query(f'userId == {numerox}'), consolidated_dfmi.head(300)])
        consolidated_dfmi = pd.concat([consolidated_dfmi.query(f'userId == {numerox}'), consolidated_dfmi.head(1000)])
        consolidated_dfmi = consolidated_dfmi.loc[~consolidated_dfmi.index.duplicated(keep='first')]
        consolidated_dfmi = consolidated_dfmi.fillna(0)


        def computeNearestNeighbor(dataframe, target_user, distance_metric=cityblock):
            distances = np.zeros(len(dataframe))
            target_row = dataframe.loc[target_user]  
            for i, (index, row) in enumerate(dataframe.iterrows()):
                if index == target_user:
                    continue  
                
                non_zero_values = (target_row != 0) & (row != 0)
                distance = distance_metric(target_row[non_zero_values].fillna(0), row[non_zero_values].fillna(0))
                distances[i] = distance
            
            sorted_indices = np.argsort(distances)
            sorted_distances = distances[sorted_indices]
            return list(zip(dataframe.index[sorted_indices], sorted_distances))
        

        target_user_id = numerox
        neighborsmi = computeNearestNeighbor(consolidated_dfmi, target_user_id)
        diccionario_resultante = dict(neighborsmi)
        valoresfinal = diccionario_resultante

        #pruebas
        cd2 = pd.DataFrame(neighborsmi)
        cd2.columns = ['Id_user', 'Distancias']

        primeros = cd2['Id_user'].unique().tolist()[:10] #lista de 10 primeros usuarios
        primeros.append(target_user_id)

        resul = peli.query('userId in @primeros') # filtra todos los datos donde aparecen esos 10 usuarios
        #newx = resul.query('rating == 5.0')['movieId'].drop_duplicates()
        newx = resul['movieId'].drop_duplicates() #elimanmos peliculas que el usauario ya vio

        #covertmos los resultados de las peliculas a diccionario
        valores_unicos = newx.values

        diccionario_recomendada = {1:2  ,3:4}
        for indice, valor in enumerate(valores_unicos):
            diccionario_recomendada[indice + 1] = valor
            if indice == 29:  
                break
        peliculasp = diccionario_recomendada

        
        #dictionary_final = dict(zip(newx.index, newx.values))
        #peliculasp = dictionary_final


        redis_conn.set('valoresfinal', json.dumps(valoresfinal))
        #redis_conn.set('peliculas', json.dumps(peliculasp))
        #redis_conn.set('peliculas', json.dumps(dictionary_final))
        redis_conn.set('peliculas', json.dumps(peliculasp))

        return jsonify(valoresfinal)
    else:
        return jsonify({"mensaje": "Esta ruta solo acepta solicitudes POST"})
#----------------------------------------------------------------



@app.route('/api/valor', methods=['GET'])
def get_users():
    # Intenta recuperar datos desde Redis
    cached_data = redis_conn.get('valoresfinal') 
    if cached_data:
        return jsonify(json.loads(cached_data))
    else:
        return jsonify({"mensaje": "No hay valores finales almacenados en Redis"})

@app.route('/api/peliculas', methods=['GET'])
def get_peliculas():
    peliculas_cached = redis_conn.get('peliculas') 
    if peliculas_cached:
        return jsonify(json.loads(peliculas_cached))
    else:
        return jsonify({"mensaje": "No hay peliculas finales almacenados en Redis"})
    

@app.route('/api/csv', methods=['GET'])
def get_csv():
    csv_cached = redis_conn.get('csv') 
    if csv_cached:
        csvx = json.loads(csv_cached)
        return jsonify(csvx)
    else:
        return jsonify({"mensaje": "No hay valores finales almacenados en Redis"})


app.run(host="0.0.0.0")
