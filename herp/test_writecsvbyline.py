import csv
import os
import random

years = 5
episodes = 100
steps = 3
agents = 10
abs_tot_ag = 15
file_out = "C:/Users/arr18sep/Desktop/pollination"

for year in range(years):
    for episode in range(episodes):
        for step in range(steps):
            for agent in range(agents):
                agent_action = random.randrange(0,5)
                agent_state = "FFT"
                agent_perf = random.random() + random.randrange(1000,2000)
                
                this_line = {}
                this_line["year"] = year
                this_line["episode"] = episode
                this_line["step"] = step
                this_line["agent_id"] = agent
                this_line["action"] = agent_action
                this_line["state"] = agent_state
                this_line["perf"] = agent_perf
                
                my_csvfile = file_out + "//" + "test_outdat.csv"
                newfile = not os.path.isfile(my_csvfile)
                
                with open(my_csvfile, 'a', newline='') as f:  # You will need 'wb' mode in Python 2.x
                    w = csv.DictWriter(f, this_line.keys())
                    if newfile:
                        w.writeheader()
                    w.writerow(this_line)
                    
# Open the csv and execute the file
for year in range(years):
    for episode in range(episodes):
        for step in range(steps):
            # Check if csv recover file exists
            my_savepath = file_out + "//" + "test_outdat.csv"
            if os.path.isfile(my_savepath):
                # Get dictionary from csv
                with open(my_savepath, 'r') as file:
                    dict_reader = csv.DictReader(file)
                    list_of_dict = list(dict_reader)            
                
                # Determine if the current iteration has been visited
                involved_ag = []
                agent_ids = []
                for dct in list_of_dict: # iterate trhough rows
                    # Has the current year_episode_step been visited?                    
                    if dct["year"] == str(year) and dct["episode"] == str(episode) and dct["step"] == str(step):
                        # Only take fields of interest
                        selected_dct = {key: dct[key] for key in dct.keys() & {'agent_id', 'action', 'state', 'perf'}}
                        agent_ids.append(int(dct["agent_id"]))
                        involved_ag.append(selected_dct)
                
                if len(involved_ag) > 0:
                    evaluated_before = True
                    #print (involved_ag)
                else:
                    evaluated_before = False
                    
                # Turn saved IDs of participating agents to int to iterate
                all_perf = [None for i in range(abs_tot_ag)]
                all_actions = [None for i in range(abs_tot_ag)]                
                              
                for agent in agent_ids:

                    for row_line in involved_ag:
                        if int(row_line["agent_id"]) == agent:
                            all_perf[agent] = row_line["perf"]
                            all_actions[agent] = row_line['action']
            # # If it does not, we have not visited this iteration
            # else:
            #     evaluated_before = False

winact_rec = [{} for agent_num in range(abs_tot_ag)]

my_winningpath = file_out  + "\\" + "winning_policy"
with open(my_winningpath, 'w', newline='') as out_file:
    fc = csv.DictWriter(out_file, fieldnames=[i for i in range(years)])
    fc.writeheader() # The keys are the agent ids, so will be the header
    fc.writerows(winact_rec) # number of rows is different for each agent