#! /urs/bin/env python3
# coding: utf-8

'''
AEP : ASSISTANT AU RECALLAGE DES CANALISATIONS 
Auteur        : Cécile Gayet
Date          : 28/05/2020
Version       : 1
Compatibilité : Qgis 3
But           : Recaller un linéaire en entrée sur des points topographiques
Utilisation   : DANS LA PARTIE DONNEES D'ENTREE : 
                1 - Renseigner la couche de canalisations             (ligne 33)
                2 - Renseigner la couche de points topographiques     (ligne 34)
                3 - Renseigner l'identifiant unique des canalisations (ligne 35)
                4 - Renseigner le filtre pour les points topo à garder(ligne 36)
                5 - Lancer le script (Clic sur la flèche verte de cette fenêtre)
Entrées       : Couche de canalisations, points topographiques complets, 
                identifiant unique des canalisations
Sorties       : - Une couche linéaire temporaire = RESULTAT_CANALISATIONS
                  contenant les canalisations recallées sur les points 
                  topographiques en entrée 
                - une couche ponctuelle temporaire = A_RECALER_MANUELLEMENT
                  contenant les points topographiques n'ayant pas de sommets 
                  diponibles où se substituer
'''

#_______________________________________________________________________________

####                             DONNEES D'ENTREE                           ####


#Renseigner les données d'entrée : 
canalisation = "AEP_CANA"
points_topo  = "09-09-2019-CCTOVAL_KevinH__CSV LEICA Export_V4"
id_cana      = "OBJECTID"
filtre       = "Profondeur like '%BRANCHEMENT%' or Profondeur like 'VANNE%'    \
or Profondeur like '%VENTOUSE%' or Profondeur like '%PURGE%'or Profondeur like \
'%VIDANGE%' or Profondeur like '%PI%' or Profondeur like '%BI%'" 

#AIDE : 

#     - canalisation doit contenir le nom exact de la couche de canalisations
#     - topo doit contenir le nom exact de la couche de points topographiques
#       Il doit obligaoirement avoir un champ nommé exactement 'X'(pas X_RELEVE)
#     - id_cana doit contenir le nom de l'identifiant unique de la canalisation
#     - filtre contient le formule qui va être utilisée pour ne prélever que les
#       points topographiques qui vont se trouver le long de la canalisation. 
#       exemple : 
#       filtre = " OBJET IN ('BRT', 'PURGE', 'VANNE', 'VENTOUSE', 'PI', 'BI') "

#       Tous les noms doivent être entre guillemets


#_______________________________________________________________________________

####                             PARTIE FONCTIONS                           ####

#Imports de modules
import processing
from   qgis.core  import QgsProject
import PyQt5

def extraire_sommets(canalisation) : 
    '''Extrait les sommets d'une couche selon ses paramètres en entrée
    Entrées : canalisations
    Sorties : sommets des linéaires avec un identifiant unique
    '''
    
    #Extraction des sommets de la ligne
    points = processing.run('native:extractvertices', 
                            {'INPUT'   : canalisation,
                             'OUTPUT'  : QgsProcessing.TEMPORARY_OUTPUT 
                             })
    
    return points['OUTPUT']

def creation_champ(couche, nom_champ) : 
    '''Crée la colonne de nom nom_champ dans la couche en entrée'''
    
    couche.dataProvider().addAttributes([QgsField(nom_champ, QVariant.String)])
    couche.updateFields()                                #Rafraîchit

def identifiant_unique(couche, champ_id) : 
    '''Modifie la couche en entrée un identifiant unique dans la colonne
    champ_id'''

    field_index = couche.dataProvider().fieldNameIndex(champ_id) #Choix du champ
    couche.startEditing()                                        #Mode édition
    count = 1                                            #Première valeur d'id
    for feature in couche.getFeatures():                 #Remplissage de la col
        _     = couche.changeAttributeValue(feature.id(),field_index,count)
        count +=1

def maj_champ(couche, nom_champ, valeur) : 
    '''Met à jour la colonne nom_champ dans couche avec la valeur en entrée'''
    field_index = couche.dataProvider().fieldNameIndex(nom_champ)
    couche.startEditing()                                 #Mode édition
    for feature in couche.getFeatures():                  #Remplissage de la col
        _     = couche.changeAttributeValue(feature.id(),field_index,valeur)


def jointure_proche_sommet(points1, points2) : 
    '''Joint la couche des regards avec une couche de points en entrée
    Sortie : Couche temporaire issue de la jointure au plus proche voisin'''
    jointure = processing.run('native:joinbynearest', 
                              {'INPUT'       : points1,
                               'INPUT_2'     : points2, 
                               'PREDICATE'   : '2', 
                               'NEIGHBORS': 1,
                               'PREFIX'      : '',
                               'OUTPUT'      : QgsProcessing.TEMPORARY_OUTPUT 
                               })
    return jointure['OUTPUT']


def separer_doublons(couche, champ) : 
    '''Divise la couche selon ses doublons dans un champs de la table : rend une
    couche sans doublons et celle des doublons'''
    jointure = processing.run('native:removeduplicatesbyattribute', 
                              {'INPUT'      : couche,
                               'FIELDS'     : champ, 
                               'OUTPUT'     : QgsProcessing.TEMPORARY_OUTPUT, 
                               'DUPLICATES' : QgsProcessing.TEMPORARY_OUTPUT 
                               })
    
    return jointure['OUTPUT'], jointure['DUPLICATES']


def points_vers_lignes(points, id_cana) : 
    '''Transforme une couche de points en couche de lignes'''
    ligne = processing.run('qgis:pointstopath', 
                           {'INPUT'       : points, 
                            'ORDER_FIELD' : 'vertex_index', 
                            'GROUP_FIELD' : id_cana, 
                            'OUTPUT'      : QgsProcessing.TEMPORARY_OUTPUT 
                            })
    
    return ligne['OUTPUT']


def jointure_attributaire(couche1, couche2, champ_jointure) :
    '''Jointure attributaire de la couche canalisation et points sur les champs
    le champ de jointure'''
    
    # Fonction de jointure attributaire
    jointure = processing.run("native:joinattributestable", 
                             {'INPUT'          : couche1,
                              'FIELD'          : champ_jointure,
                              'INPUT_2'        : couche2,
                              'FIELD_2'        : champ_jointure,
                              'OUTPUT'         : QgsProcessing.TEMPORARY_OUTPUT
                              })
    return jointure['OUTPUT']


def topo_pertinente(topo, filtre) : 
    '''Récupération des points topographiques qui sont intesectés à la 
    canalisation'''
    
    #Effectuer l'extraction sur ce filtre
    topo_res = processing.run('native:extractbyexpression', 
                              {'EXPRESSION' : filtre, 
                               'INPUT'      : topo,
                               'OUTPUT'     : QgsProcessing.TEMPORARY_OUTPUT
                               })
    
    return topo_res['OUTPUT']

def nettoyer(couche_orig, points_sales) : 
    '''Nettoie la couche en supprimant des champs non désirables ajoutés pendant
    les traitements'''
    compte_orig = 0
    compte_sale = 0
    for field in couche_orig.fields():
        compte_orig += 1
    
    for field in points_sales.fields():
        compte_sale += 1
    
    for i in range(compte_orig, compte_sale) : 
        points_sales.dataProvider().deleteAttributes([compte_orig])
        points_sales.updateFields()

def nettoyer2(couche, id_cana) : 
    '''Ne garde que les champs d'indentifiant de ligne d'origine et 
    vertex_index'''
    count = 0                        #Pour la construction de l'index des champs
    liste = []                       #Contient l'index des champs à effacer
    for field in couche.fields(): #Pour chaque champ
        if field.name() == 'vertex_index'                                      \
        or field.name() == id_cana : #Repérage des champs à effacer
            print("Un champ est exclus")
        else : 
            liste.append(count)      #La liste d'index à effacer se remplit
        count += 1 
    print("La liste de l'index des champs est : \n", liste) #Pour contrôle
    
    #Efface les attributs de la liste
    couche.dataProvider().deleteAttributes(liste)
    couche.updateFields()                                  #Rafraîchit la couche
    
    return couche

def extraire_entites(couche) : 
    '''Efface des entités quand le champ 'X' de la couche est nul'''
    res = processing.run('native:extractbyattribute',
                         {'FIELD': 'X',
                          'INPUT': couche,
                          'OPERATOR': 8,
                          'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                          })
    
    return res['OUTPUT']


def copier_coller_enties(couche_source, couche_cible) : 
    '''copie colle des entités'''

    features = []
    for feature in couche_source.getFeatures():
        features.append(feature)
    couche_cible.startEditing()
    data_provider = couche_cible.dataProvider()
    data_provider.addFeatures(features)
    couche_cible.commitChanges()
    
    return couche_cible


def comptage(couche) : 
    '''Compte du nombre d'entités de la couche en entrée'''
    compte  = 0
    for f in couche.getFeatures() : #Pour chaque entité
        compte += 1                 #Incrémente un compteur
    return compte
        
def pop_up(chiffre1, chiffre2, chiffre3) : 
    '''Affiche un message d'information dans une pop up'''
    #Information
    MsgBx = QMessageBox.information(None, 
                                    'TEST DE CONTROLE',
                                    'Il y avait ' 
                                    + str(chiffre1) 
                                    +' entités dans la couche source \
et on en décompte '
                                    + str(chiffre2) + ' dans le linéaire en \
résultat. \n\n Il y a ' + str(chiffre3) + ' points topographiques non pris en \
compte dans le recalage (couche A_RECALER_MANUELLEMENT). \n\n ATTENTION : les \
couches en résultat sont des couches temporaires. Pensez à les enregistrer' )

    
def prepa_points(cana, topo, id_cana, filtre) : 
    '''Prépare des couches de ponctuels pour les mettre sous forme de lignes
    Entrées : cana = Canalisation, topo = topographie, id_cana = identifiant 
    unique de canalisation, filtre = formule pour garder les points 
    topographiques pertinents
    Sortie : res      = points pour la traçage de la canalisation 
             doublons = Points exclus du traçage'''
    
    sommets      = extraire_sommets(cana)    #Extraction des sommets de la ligne
    creation_champ(cana, 'UI')                  #Création du champs UI
    identifiant_unique(sommets, 'UI')           #Identification des sommets (UI)
    sommets_topo = topo_pertinente(topo, filtre) #Choix de la topo pertinente
    
    #jointure au plus proche sommet
    sommets_res  = jointure_proche_sommet(sommets_topo, sommets)
    
    #Séparation des doublons
    sommets_res  = separer_doublons(sommets_res, 'UI') #Renvoie deux couches : 
    points_res   = sommets_res[0]                      #Les points valides
    doublons     = sommets_res[1]                      #Les points non attribués
    nettoyer(topo, doublons)                      #Nettoie la table des doublons
    doublons.setName('A_RECALER_MANUELLEMENT')    #Renommage des doublons
    
    #Jointure des points topo
    points = jointure_attributaire(sommets, points_res, 'UI')
    
    #Quand il existe un ancien point, supression
    #X est non null, alors il y a un point topo, on sélectionne et on supprime
    points = extraire_entites(points)
    points   = nettoyer2(points, id_cana)           #Nettoyage de la table
    resultat = nettoyer2(sommets_res[0], id_cana)   #Nettoyage de la table
    
    #Copier/coller des points topo nouveaux
    res = copier_coller_enties(points, resultat)
    res.setName('POINTS_PRETS')                     #Renommage de res
    
    return res, doublons

def main(cana, topo, id_cana, filtre) :
    '''Dessine la canalisation sur les points topographiques en entrée
    Entrées : cana = Canalisation, topo = topographie, id_cana = identifiant 
    unique de canalisation, filtre = formule pour garder les points 
    topographiques pertinents
    Sortie  : - cana_recalee = nouvelle canalisation calée sur des poinst topo
              - doublons     = Points exclus du traçage'''
    
    #Mise en forme des couches de points
    points_prets    = prepa_points(cana, topo, id_cana, filtre)
    resultat_points = points_prets[0]
    doublons        = points_prets[1]
    
    #Points vers lignes : 
    cana_recalee = points_vers_lignes(resultat_points, id_cana)
    #Jointure attributaire pour récupérer la sémantique des linéaires
    cana_recalee = jointure_attributaire(cana_recalee, cana, id_cana)
    cana_recalee.setName('CANALISATION_RECALEE')        #Renommage de la couche
    
    return cana_recalee, doublons

def info(couche1, couche2, couche3) : 
    '''Renvoie une pop up avec les informaions de contrôle : 
    Le nombre d'entités dans la couche linéaire source 
    Le nombre d'entités dans la couche linéaire en sortie
    Le nombre d'entités dans la couche pontuelle de la topo non intégrée'''
    nb_source = comptage(couche1) # compte le nombre d'entités dans cana
    nb_cible  = comptage(couche2) # compte le nombre d'entités dans cana_recalee
    doublons  = comptage(couche3) # compte le nombre d'entités dans doublons
    infobulle = pop_up(nb_source, nb_cible, doublons) #Affichage info-bulle

#_______________________________________________________________________________

####                             SCRIPT PRINCIPAL                           ####

#Récupération de la couche de nom contenu dans la variable canalisation et de la
#couche de nom contenu dans la variable points_topo
cana = QgsProject.instance().mapLayersByName(canalisation)[0]
topo = QgsProject.instance().mapLayersByName(points_topo)[0]

#Lancement de la création du linéaire recalé
resultat = main(cana, topo, id_cana, filtre)[0]
doublons = main(cana, topo, id_cana, filtre)[1]

#Ajout des couches dans le projet
QgsProject.instance().addMapLayer(resultat)    #Canalisations recallées
QgsProject.instance().addMapLayer(doublons)    #A recaller manuellement

#Pop up : comparaison entre le nombre de canalisations en entrée et en résultat 
info(cana, resultat, doublons)