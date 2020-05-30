#! /urs/bin/env python3
# coding: utf-8

'''
AMONT AVAL D'UN LINEAIRE
Auteur        : Cécile Gayet
Date          : 20/05/2020
Version       : 4
Compatibilité : Qgis 3
But           : Obtenir des informations sur l'amont et l'aval d'une couche linéaire
Utilisation   : DANS LA PARTIE DONNEES D'ENTREE : 
                1 - Renseigner la couche de canalisations             (ligne 26)
                2 - Renseigner la couche de regards                   (ligne 27)
                3 - Mentionner les champs provenant de la couche 
                    des regards à joindre à la canalisation           (ligne 28)
                4 - Renseigner l'identifiant unique des canalisations (ligne 29)
                5 - Lancer le script (flèche verte de cette fenêtre)
Entrées       : Couche de canalisations, de regards, champs de la couche de
                regards et identifiant unique des canalisations
Sorties       : Une couche linéaire temporaire = RESULTAT_CANALISATIONS
                contenant les canalisations avec les champs des regards amont et
                aval joints. 
'''

#_______________________________________________________________________________

####                             DONNEES D'ENTREE                           ####


#Renseigner les données d'entrée : 
canalisation   = "CANALISATIONS"
regard         = "REGARDS"
champs         = ["NUM_REG", "Z_RELEVE", "PROFONDEUR", "CLASSE"]
ID_unique_cana = "num_tron"

#AIDE : 

#     - canalisation doit contenir le nom exact de la couche de canalisations
#     - regard doit contenir le nom exact de la couche de regards
#     - champs est l'ensemble des champs issus de la couche  des regards à 
#       retrouver dans le résultat
#     - ID_unique_cana est l'identifiant unique de la couche de canalisations

#       Tous les noms doivent être entre guillemets
#       Il faut bien mettre la liste des champs entre crochet, séparés par des
#       virgules et entre guillemets. ex : ["blabla","blabla"]


#_______________________________________________________________________________

####                             PARTIE FONCTIONS                           ####

#Imports de modules
import processing
from qgis.core import QgsProject


def extraire_sommets(couche, ind) : 
    '''Extrait les sommets d'une couche selon ses paramètres en entrée
    couche : la couche de lignes dans laquelle les sommets sont extraits
    ind = 0 si on veut le premier sommet / -1 si on veut le dernier sommet
    '''
    
    points = processing.run('qgis:extractspecificvertices', 
                            {'INPUT'   : couche,
                             'VERTICES': str(ind),
                             'OUTPUT'  : QgsProcessing.TEMPORARY_OUTPUT 
                             })
                            
    return points['OUTPUT']

def jointure_regards(regards, extremites, champs) : 
    '''Joint la couche des regards avec une couche de points en entrée
    Sortie : Couche temporaire'''
    jointure = processing.run('qgis:joinattributesbylocation', 
                              {'INPUT'       : regards,
                               'JOIN'        : extremites, 
                               'PREDICATE'   : '2', 
                               'JOIN_FIELDS' : champs,
                               'METHOD'      : 1, 
                               'PREFIX'      : '_',
                               'OUTPUT'      : QgsProcessing.TEMPORARY_OUTPUT 
                               })
    print(jointure)
    return jointure['OUTPUT']

def jointure_attributaire(cana, point, champ_jointure, champs_joints, prefixe) :
    '''Jointure attributaire de la couche canalisation et points sur les champs
    champ_cana et chmp_point'''
    
    # Fonction de jointure attributaire
    jointure = processing.run("native:joinattributestable", 
                             {'INPUT'          : cana,
                              'FIELD'          : champ_jointure,
                              'INPUT_2'        : point,
                              'FIELD_2'        : champ_jointure,
                              'FIELDS_TO_COPY' : champs_joints,
                              'METHOD'         : 1,
                              'PREFIX'         : prefixe,
                              'OUTPUT'         : QgsProcessing.TEMPORARY_OUTPUT
                              })
    return jointure['OUTPUT']

def extremites(cana, rega, champs) : 
    '''Sort les sommets amonts et aval d'une couche et les ajoute au projet
    sortie : liste de couches temporaires'''
    #Extraction des sommets
    point_amont = extraire_sommets(cana, -1)
    point_aval  = extraire_sommets(cana,  0)
    
    #Jointure avec les regards
    amont = jointure_regards( point_amont, rega, champs)
    aval  = jointure_regards( point_aval,  rega, champs)

    return amont, aval

def canalisations_jointes(cana, rega, champs, ID_unique_cana) :
    '''Jointure des champs utiles dans les canalisations'''
    #Mise en route de la fonction extremites et stokage du résultat dans la 
    #variable 'points'
    points = extremites(cana, rega, champs)

    #Renommage des champs avec le préfixe de la jointure par localisation entre 
    #les points amont-aval et les regards
    for i in range(len(champs)) : 
        champs[i] = '_' + champs[i]

    #Jointure attributaire entre la couche de canalisation et les points amont 
    cana_step_1 = jointure_attributaire(cana      , points[1], ID_unique_cana,
                                        champs, 'AM')
    
    #Jointure attributaire entre la couche de canalisation et les points amont 
    cana_step_2  = jointure_attributaire(cana_step_1, points[0], ID_unique_cana,
                                         champs, 'AV')
                                        
    #Renommage de la couche (nom de couche par défaut = 'Couche issue de la 
    #jointure spatiale')
    cana_step_2.setName('RESULTAT_CANALISATIONS')
    
    return cana_step_2

#_______________________________________________________________________________

####                             SCRIPT PRINCIPAL                           ####

#Récupération de la couche de nom contenu dans la variable canalisation et de la
#couche de nom contenu dans la variable regard
cana = QgsProject.instance().mapLayersByName(canalisation)[0]
rega = QgsProject.instance().mapLayersByName(regard)[0]

#Lancement de l'insertion des champs des regards amont et aval dans les canalis
res_canalisations = canalisations_jointes(cana, rega, champs, ID_unique_cana)

#Ajout des couches dans le projet
QgsProject.instance().addMapLayer(res_canalisations)
