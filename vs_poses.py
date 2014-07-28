#!/usr/bin/env python


###############################################################################
#
#   Uses the results.csv previously generated to locate the top X docking poses
#   following a VS. Loads them using ICM and saves the poses wanted to a single
#   .pdb file. Also saves the receptor to that .pdb file. That file can then be
#   opened using ICM or an other molecular viewer.
#
#   Thomas Coudrat, July 2014
#
###############################################################################


import csv
import sys
import os
import glob
import shutil
import argparse
import socket
from subprocess import check_output, STDOUT, CalledProcessError


def main():
    """
    Run the scripts
    """

    # Get the arguments and paths
    resultsPath, X, ligIDs = parseArgs()
    icmBin = setPath()

    # Fix paths
    cwd = os.getcwd()
    vsPath = os.path.dirname(cwd + "/" + resultsPath)
    projName = os.path.basename(os.path.dirname(cwd + "/" + resultsPath))

    # Parse the VS results
    resDataAll = parseResultsCsv(resultsPath)

    # Select results, the top X and optionally specific ligIDs
    resDataSel = selectResults(resDataAll, X, ligIDs)

    # Print the selected results
    printResults(resDataSel)

    # Get the list of poses to pick per repeat directory
    repeatsRes = posesPerRepeat(resDataSel)

    # Load those poses and save them in the /poses directory
    loadAnswersWritePoses(repeatsRes, vsPath, projName, icmBin)

    # Now load and write the receptor (binding pocket)
    recObName = projName + "_rec"
    recObPath = vsPath + "/vs_setup/" + recObName + ".ob"
    recPdbPath = vsPath + "/poses/" + recObName + ".pdb"
    readAndWrite([recObPath], [["a_" + recObName + ".", recPdbPath]], icmBin)
    print


def parseArgs():
    """
    Create arguments and parse them
    """
    # Parsing description
    descr = "Extract docking poses from a VS in .pdb format"
    descr_resultsPath = "Results file of the VS in .csv format"
    descr_X = "Extract the top X poses"
    descr_ligIDs = "Optional ligIDs docking poses to be extracted"

    # Define arguments
    parser = argparse.ArgumentParser(description=descr)
    parser.add_argument("resultsPath", help=descr_resultsPath)
    parser.add_argument("X", help=descr_X)
    parser.add_argument("--ligIDs", help=descr_ligIDs)

    # Parse arguments
    args = parser.parse_args()
    resultsPath = args.resultsPath
    X = int(args.X)
    ligIDs = args.ligIDs

    # Make ligIDs a list of IDs integers
    if ligIDs:
        ligIDs = makeIDlist(ligIDs)
        # print ligIDs
        # sys.exit()

    return resultsPath, X, ligIDs


def makeIDlist(stringID):
    """
    Get a string defining which IDs to be generated into a list
    """

    # This stores the range of IDs into a list
    rangeID = []

    IDportions = stringID.split(",")

    for portion in IDportions:
        # Treat ranges of IDs
        if "-" in portion:
            start, end = portion.split("-")
            start = int(start)
            end = int(end)
            # Do not add the value 0 to the list
            if start == 0 or end == 0:
                pass
            else:
                rangeID = rangeID + range(start, end + 1)
        # Treat single IDs
        else:
            portion = int(portion)
            # Do not add the value 0 to the list
            if portion == 0:
                pass
            else:
                rangeID.append(int(portion))

    return rangeID


def setPath():
    """
    Figure out which machine this script is executed on, and use the
    corresponding executable path
    """

    hostname = socket.gethostname()

    icmDesk = "/usr/icm-3.7-3b/icm64"
    icmLap = "/home/thomas/bin/icm-3.8-0/icm64"
    icmVlsci = "/vlsci/VR0024/tcoudrat/bin/icm-3.7-3b/icm64"
    icmMcc = "/nfs/home/hpcpharm/tcoudrat/bin/icm-3.7-3b/icm64"

    if hostname == "linux-T1650":
        icmBin = icmDesk
    elif hostname == "Ideapad":
        icmBin = icmLap
    elif hostname == "barcoo":
        icmBin = icmVlsci
    elif hostname == "msgln4.its.monash.edu.au":
        icmBin = icmMcc
    elif hostname == "msgln6.its.monash.edu.au":
        icmBin = icmMcc
    else:
        print "System not recognised, update script to include executable path"
        sys.exit()

    return icmBin


def parseResultsCsv(resPath):
    """
    Read the resultsPath, and extract the location (which repeat) of each ligand
    for which the docking pose should be extracted
    """

    # Read data with the csv reader
    resFile = open(resPath, "r")
    resData = csv.reader(resFile)
    resData = [row for row in resData]
    resFile.close()

    resLen = len(resData)

    # Generate a selection of the top X docked ligands, selecting only the
    # ligandID [0], the ICM score [9], and the repeat directory [-1]
    resDataAll = [[ID, eval(row[0]), eval(row[9]), row[-1]] for row, ID in
                  zip(resData[1:], range(1, resLen))]

    return resDataAll


def selectResults(resDataAll, X, ligIDs):
    """
    Make a selection of the top X VS results, also as optional ligIDs
    """

    # First select the top X ligands
    resDataTop = [row for row in resDataAll[0:X]]

    # If the ligID flag was used, select by ligIDs, the ligID is in row[1]
    # and return a combined list: if a selected ligID is within the top X, there
    # will be a duplicate. However when processed the .pdb docking pose will be
    # written then overwritten, resulting in the result expected
    if ligIDs:
        resDataID = [row for row in resDataAll if row[1] in ligIDs]
        return resDataTop + resDataID
    # Otherwise just return the 'top' list
    else:
        return resDataTop


def printResults(resData):
    """
    Takes in results and prints them out
    """

    print
    print "Rank\tID\tScore\tRepeat"
    for res in resData:
        print res[0], "\t", res[1], "\t", res[2], "\t", res[3]


def posesPerRepeat(resData):
    """
    Create a list for each repeat directory with the ordered list of ligIDs that
    should be extracted to be part of the results
    """

    # Store the ligand data into a dictionary where the keys are repeat numbers
    repeatsRes = {}

    for row in resData:
        rep = row[3]
        keys = repeatsRes.keys()
        # if the repeat already exists in the keys, add the row to the list
        if rep in keys:
            repeatsRes[rep].append(row)
            repeatsRes[rep].sort
        # otherwise create a new list with that row
        else:
            repeatsRes[rep] = [row]

    return repeatsRes


def loadAnswersWritePoses(repeatsRes, vsPath, projName, icmBin):
    """
    Walk through repeat directories, and load each
    """
    # Create the results directory, delete it if already exists
    resultsPath = vsPath + "/poses/"
    if os.path.exists(resultsPath):
        shutil.rmtree(resultsPath)
    os.makedirs(resultsPath)

    print

    for key in repeatsRes.keys():
        # Update progress
        # print "Extracting", len(repeatsRes[key]), "poses from repeat #", key

        # Get the ob file list
        repPath = vsPath + "/" + key + "/"
        # Ligands found in that repeat
        # print repeatsRes[key], "LIGANDS FOUND IN THAT REPEAT"
        ligsInfo = [[row[1], ""] for row in repeatsRes[key]]
        obFileList = getAnswersList(repPath, ligsInfo)
        # print repeatsRes[key], "After"

        # print obFileList

        # Get the pdb file list
        pdbFileList = []
        for row in repeatsRes[key]:
            # print row
            ligPos = row[0]
            ligScore = row[2]
            ligID = row[1]
            pdbFilePath = resultsPath + str(ligPos) + "_" + str(ligScore) + \
                "_" + str(ligID) + ".pdb"
            icmName = "a_" + projName.replace("-", "_") + str(ligID) + "."

            pdbFileList.append([icmName, pdbFilePath])

        readAndWrite(obFileList, pdbFileList, icmBin)


def getAnswersList(repPath, ligsInfo):
    """
    Given a repeat directory path and a list of ligand IDs, return the list
    of VS answers (.ob files) that contain all the ligand IDs provided.
    """

    # Get a list of all the files, and make is an sorted list
    allObFiles = glob.glob(repPath + "*_answers*.ob")
    allObFiles = [[obFile, int(obFile.split("_answers")[1].replace(".ob", ""))]
                  for obFile in allObFiles]
    sortedObFiles = sorted(allObFiles, key=lambda obFile: obFile[1],
                           reverse=True)
    for obFile in sortedObFiles:
        obFilePath = obFile[0]
        obFileStart = obFile[1]

    # Loop over the ligsInfo list, which contains
    # ligInfo[0] = the ligand ID number
    # ligInfo[1] = an empty string that is used to store the path to the
    # corresponding .ob file to be loaded
    # print
    for lig in ligsInfo:
        # print lig
        ligID = lig[0]
        # answerPath = ligInfo[1]

        previousObStart = 999999999999999999999999999999999999999999999999

        # Loop over all answers file, and for each
        for obFile in sortedObFiles:
            obFileStart = obFile[1]
            obFilePath = obFile[0]

            # print
            # print obFileStart, 'current'
            # print previousObStart, 'prev'
            # print obFilePath, 'path'
            # print ligID, 'ligID'
            # print

            # If the ligand ID number is between between the start of this file
            # and the start of the previous file (part of the current file)
            # print obFileStart, previousObStart
            if ligID >= obFileStart and ligID < previousObStart:
                lig[1] = obFilePath
                # print obFilePath

            previousObStart = obFileStart

        # print "ObPath", lig
        # print

    return list(set([lig[1] for lig in ligsInfo]))


def readAndWrite(obFileList, pdbFileList, icmBin):
    """
    Get the information of which *.ob files to read, and which *.pdb files from
    the loaded molecules to write.
    Edit a temporary version of the ICM script with that information, and
    execute it.
    This script is writen and executed for each repeat, selecting only the
    poses from each of those repeats
    """

    # Create temp script
    icmScript = open("./temp.icm", "w")
    icmScript.write('call "_startup"\n')
    # Add the ob file loading part
    icmScript.write("\n# OPENING FILES\n")
    for obFile in obFileList:
        print "loading:", obFile
        icmScript.write('openFile "' + obFile + '"\n')
    # Add the pdb file saving part
    icmScript.write("\n# WRITING FILES\n")
    for pdbFile in pdbFileList:
        icmScript.write('write pdb ' + pdbFile[0] + ' "' + pdbFile[1] + '"\n')
    icmScript.write("\nquit")
    icmScript.close()

    # Execute temp script
    try:
        check_output(icmBin + " -s ./temp.icm", stderr=STDOUT, shell=True)
    except CalledProcessError, e:
        print e.output
        sys.exit()

    # Delete temp script
    os.remove("./temp.icm")


if __name__ == "__main__":
    main()