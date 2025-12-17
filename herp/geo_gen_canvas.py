'''This module has the base geometrical classes for incremental 
dwelling simulation. These are Blocks and Lots.'''

import Rhino
import System
import random
import itertools

#### General functions #####
def RemoveSubL(lst):
    return list(map(list, (set(map(lambda x: tuple(sorted(x)), lst)))))

##### Classes #####
# SPACE NEEDED MUST BE A LIST OF SIZE NR_OF AGENTS!, Add a budget input of the same format!
class BlockOfAgents:
    # Initializer with plot location
    def __init__(self, blockorigx, blockorigy, lotsizex, lotsizey, module, coreorigx, coreorigy, coresizex, coresizey,
                 maxheight, NrlotsOnSide, doubleside, mainsideXorY, nr_vertix_match, space_needed, w_cost, r_cost):
        self.WallsCost = w_cost
        self.RoofCost = r_cost
        self.BlockOrigX = blockorigx
        self.BlockOrigY = blockorigx
        self.LotsOnSide = NrlotsOnSide
        self.DoubleSide = doubleside
        self.Direction = mainsideXorY
        self.LotsModule = module
        self.LotsSizeX = lotsizex
        self.LotsSizeY = lotsizey
        self.LotsCoresOrigX = coreorigx
        self.LotsCoresOrigY = coreorigy
        self.LotsCoresSizeX = coresizex
        self.LotsCoresSizeY = coresizey
        self.LotsMaxH = maxheight
        self.SpaceNeeded = space_needed
        self.VerticesToMatch = nr_vertix_match

        if self.LotsOnSide <= 1:  # Single agent
            self.Lots = HHagent(self.BlockOrigX, self.BlockOrigY, self.LotsSizeX, self.LotsSizeY, self.LotsModule,
                                self.LotsCoresOrigX, self.LotsCoresOrigY, self.LotsCoresSizeX, self.LotsCoresSizeY,
                                self.LotsMaxH, self.SpaceNeeded, self.WallsCost, self.RoofCost)
            self.Breps = self.Lots.BrepCore
            # The following is looking for sc.sticky["q_tab_mem"]
            self.Qtables = self.Lots.MyQTable()  # On q-table update this variable must be replaced
            self.AbsMaxActs = self.Lots.MaxActions()
            self.AbsMaxStates = "No Joint actions when one agent"
            print (self.AbsMaxStates)
            self.ViewRange = "No view range when one agent"
            print (self.ViewRange)
            # self.Qtables = self.Lots.CreateQTable(max_states, max_acts)
        else:  # Multi-agent
            self.Lots = self.MutiplyLotsSide()
            self.AbsMaxActs = self.Lots[0].MaxActions()  # Only works if all lots are equal!
            # self.AbsMaxStates = self.GetAllJActs(self.VerticesToMatch + 1)

    def MutiplyLotsSide(self):
        # Determine the origin coordinates for the other lots
        origincoords = [[None for i in range(2)] for j in range(self.LotsOnSide - 1)]

        origx = self.BlockOrigX
        origy = self.BlockOrigY
        initial_pair = [self.BlockOrigX, self.BlockOrigY]

        if self.Direction:
            for k in range(self.LotsOnSide - 1):
                origincoords[k][0] = origx  # the first element is the x coordinate
            for l in range(self.LotsOnSide - 1):
                origincoords[l][1] = origy + (self.LotsModule * self.LotsSizeY)
                origy = origincoords[l][1]
            origincoords.append(initial_pair)
            if self.DoubleSide:
                add_coords = []
                for pair in origincoords:
                    opos_x = pair[0] + (self.LotsModule * self.LotsSizeX)
                    opos_y = pair[1]
                    newpair = [opos_x, opos_y]
                    add_coords.append(newpair)
                origincoords += add_coords
        else:
            for k in range(self.LotsOnSide - 1):
                origincoords[k][0] = origx + (self.LotsModule * self.LotsSizeX)
                origx = origincoords[k][0]
            for l in range(self.LotsOnSide - 1):
                origincoords[l][1] = origy
            origincoords.append(initial_pair)
            if self.DoubleSide:
                add_coords = []
                for pair in origincoords:
                    opos_x = pair[0]
                    opos_y = pair[1] + (self.LotsModule * self.LotsSizeY)
                    newpair = [opos_x, opos_y]
                    add_coords.append(newpair)
                origincoords += add_coords

        lots = []
        for pairs in origincoords:
            agents = HHagent(pairs[0], pairs[1], self.LotsSizeX, self.LotsSizeY, self.LotsModule, self.LotsCoresOrigX,
                             self.LotsCoresOrigY, self.LotsCoresSizeX, self.LotsCoresSizeY, self.LotsMaxH,
                             self.SpaceNeeded, self.WallsCost, self.RoofCost)
            lots.append(agents)

        return lots

    # returns a list of the indices of the lots that neighbour a particular agent
    def IdNeigbours(self, lot):  # Lot should be the numeric id of it (index)
        vertix = [[] for i in range(len(self.Lots))]

        for i in range(len(self.Lots)):
            vertices = self.Lots[i].VertixLots
            vertix[i] = vertices

        my_vertices = vertix[lot]  # I could exclude this from other list, or turn to null

        # Check if there are coincidences of less than 3 pts
        matches = []
        # Could put the matches between the above list and each sublist on a different list. If len 4>m>0, attach its index to another list
        for j in range(len(vertix)):
            match = set(my_vertices).intersection(vertix[j])  # Matching between my vertices and each other lot
            if 4 > len(match) > self.VerticesToMatch - 1:
                matches.append(j)

        return list(matches)  # Index of lots that are neighbouring

    # Returns a list of the index of agents within the range of view of all agents
    def RangeView(self):
        onRange = [[] for i in range(len(self.Lots))]
        for j in range(len(self.Lots)):
            onRange[j] = self.IdNeigbours(j)

        return onRange

    def GetBreps(self):
        breps = []
        for lot in self.Lots:
            brep = lot.OutBrep
            breps.append(brep)
        return breps

    # This function gets a list of the individual current states of all the agents
    def GetIStates(self):
        states = []  # This only contains the single-states
        for lot in self.Lots:
            c_state = lot.C_state
            states.append(c_state)
        return states

    def GetAvailActs(self):
        list_availacts = []
        for lot in self.Lots:
            c_avail_acts = lot.Poss_act
            list_availacts.append(c_avail_acts)
        return list_availacts

    # This function gets a list of combined current states per agent as string
    def GetJStates(self):
        ind_states = self.GetIStates()  # Get all current states
        combo_states = []
        # For each agent
        for i in range(len(self.Lots)):
            neigh_ids = self.IdNeigbours(i)  # Get my neigh ids
            if len(neigh_ids) > 1:
                neigh_ids.sort()
            my_istate = ind_states[i]  # Get my current state

            # Getting the current state of my neighbours
            my_neighstates = []
            for id in neigh_ids:
                neigh_state = ind_states[id]
                my_neighstates.append(neigh_state)

            # The following detects if my state or their state is null
            my_anyTs = my_istate.count('T')
            neigh_noTs = []
            for neigh_state in my_neighstates:
                counT = neigh_state.count('T')
                if counT == 0:
                    neigh_noTs.append(neigh_state)

            if my_anyTs == 0 or len(neigh_noTs) > 0:
                my_istate = 'F'  # THIS IS THE ABSOLUTE NULL STATE
            else:
                # Joining my state and their state in a str
                for state in my_neighstates:
                    tup = (my_istate, state)  # a tuples with two strings
                    stri = '_'.join(tup)  # Join the two string on the tuple
                    my_istate = stri  # replace initial list for list of joined tuples

            # append to list of joined states
            combo_states.append(my_istate)

        return combo_states

    def GetOccupiedP(self):
        ocuppiedp = []
        for lot in self.Lots:
            c_occupied = lot.NOccupiedPts
            ocuppiedp.append(c_occupied)
        return ocuppiedp

    def GetExtCost_Balance(self):
        extcost = []
        balance = []
        for lot in self.Lots:
            my_extcost = lot.WallAreaExtCost + lot.RoofAreaExtCost
            my_balance = BUDGET - my_extcost  # Budget is a global component input
            extcost.append(my_extcost)
            balance.append(my_balance)

        return [extcost, balance]

    ##### THIS FUNCTION INITIALIZES THE Q-TABLEs list, USE JUST ON FIRST ITERATION #####
    def GetMultiQtables(self,
                        abs_possible_jacts):  # abs_max_actions is universal here, could later individualize (need the data of neighbours)
        qtables = []
        for i in range(len(self.Lots)):
            neighbours_ids = self.IdNeigbours(i)  # we make sure that list is in order
            if len(neighbours_ids) > 1:
                neighbours_ids.sort()
            nr_of_neighbours = len(neighbours_ids)
            my_poss_jacts = abs_possible_jacts[nr_of_neighbours]
            my_poss_jstates = []

            for neigh_id in neighbours_ids:
                my_poss_jstates.append(self.Lots[neigh_id].MaxStates)  # This is a list for each neigh

            qtable = self.Lots[i].CreateMultiQTable(self.Lots[i].MaxStates, self.AbsMaxActs, my_poss_jacts,
                                                    my_poss_jstates)
            qtables.append(qtable)

        return qtables

    # This function is alternative to the previous, builds an initial q_Table to be incrementally enlarged
    def GetMultiQtables2(self, initial_poss_acts, initial_jstates):
        q_tables = []
        sja_tables = []
        for i in range(len(self.Lots)):
            # my_initial_state = self.Lots[i].InitState
            my_initial_state = initial_jstates[i]  # joint state string
            my_initial_actions = initial_poss_acts[i]  # possible acts on my initial state
            my_null_state = self.Lots[i].GetNullState()

            neighbours_ids = self.IdNeigbours(i)
            neighbours_ids.sort()
            my_neighs_possacts = []
            for id in neighbours_ids:
                neigh_possact = initial_poss_acts[id]
                my_neighs_possacts.append(neigh_possact)

            possible_neigh = []
            for max_acts in my_neighs_possacts:
                acts = [i for i in range(max_acts + 2)]
                possible_neigh.append(acts)

            combos = list(itertools.product(*possible_neigh))

            my_qtab = {}
            my_qtab[my_initial_state] = {}
            my_qtab[
                'F'] = None  # This is the absolute null state, if one individual state is non-manifold, joint_state = F
            my_JAstate = {}
            my_JAstate[my_initial_state] = {}
            my_JAstate['F'] = None  # This is the absolute null state
            for combo in combos:
                my_qtab[my_initial_state][combo] = [0 for k in range(0, my_initial_actions + 2)]
                my_JAstate[my_initial_state][combo] = 0

            # abs_max_possible_combos = self.GetAllJActs2(len(neighbours_ids))

            # for abs_max_combo in abs_max_possible_combos:
            # my_qtab[my_null_state][abs_max_combo] = [0 for k in range(0, my_initial_actions + 2)]
            # my_JAstate[my_initial_state][abs_max_combo] = 0

            q_tables.append(my_qtab)
            sja_tables.append(my_JAstate)

        return [q_tables, sja_tables]

    def GetInitJStates(self):
        joint_states = []
        for i in range(len(self.Lots)):
            my_istate = self.Lots[i].InitState

            # Identify my neighbours
            neighbours_ids = self.IdNeigbours(i)
            neighbours_ids.sort()

            my_neigh_strs = []
            for id in neighbours_ids:
                neigh_str = self.Lots[id].InitState  # gets the string of their individual init state
                my_neigh_strs.append(neigh_str)

            # Join my string with theirs
            for state in my_neigh_strs:
                tup = (my_istate, state)  # a tuples with two strings
                stri = '_'.join(tup)  # Join the two string on the tuple
                my_istate = stri  # replace initial list for list of joined tuples

            # append to list
            joint_states.append(my_istate)

        return joint_states

    def GetInitPossActs(self):
        possible_acts = []
        for i in range(len(self.Lots)):
            mypossacts = self.Lots[i].AvailActs(self.Lots[i].BrepCore)
            possible_acts.append(mypossacts)
        return possible_acts

    # To create max neighbour states only once
    def GetAllJActs(self, max_neigh):
        PossibleJActs = [[] for i in range(max_neigh + 1)]  # Each on a subgroup accroding to the number of neighbours

        for j in range(0, max_neigh + 1):
            # Creates a list of tuples with all the possible combinations of actions of neighbours
            # out = [p for p in itertools.product(range(ABS_MAX_ACTS + 2), repeat=j)]
            out = [p for p in itertools.product(range(self.AbsMaxActs + 2), repeat=j)]
            PossibleJActs[j] = out

        return PossibleJActs  # Input the index of YOUR number of neighbours to get all possible combos

    # Same as before but only input the number of neighbours and get no sublists
    def GetAllJActs2(self, nr_of_neigh):
        PossibleJActs = [p for p in itertools.product(range(self.AbsMaxActs + 2), repeat=nr_of_neigh)]
        return PossibleJActs

    # This function initializes the relevant data dictionaries, use only on first iteration
    def GetRelevantDatas(self, max_steps,
                         max_episodes):  # Steps and episode are universal here, could later individualize
        relevantdatas = []
        for lot in self.Lots:
            relevantdata = lot.CreateGDict2(max_steps, max_episodes)
            relevantdatas.append(relevantdata)
        return relevantdatas

    # This function gets a global relevant data list of dictionaries without depending on the agent's functions
    def GetRelevantDatas2(self, max_steps, max_episodes):
        titles = ["Agent_Id", "Countdown", "Episode", "Step", "State_0", "Action", "Joint_act", "Epsilon", "Flag",
                  "Old_q", "State_1", "Reward", "Max_future_q", "New_q", "Current_perf", "Record_Perf",
                  "Remaining_Budget", "LR", "Mod_occupied"]
        relevantdatas = [{} for i in range(max_steps * max_episodes * len(self.Lots))]

        # Assing key-values to each agent_timestep
        for dictio in relevantdatas:
            for title in titles:
                dictio[title] = None

        return relevantdatas

        # This function initializes the dictionary of visited states/joint_actions, use only on first iteration

    def GetVisitedStateJAct(self, abs_possible_jacts):
        dicts = []
        for i in range(len(self.Lots)):
            neighbours_ids = self.IdNeigbours(i)  # we make sure that list is in order
            if len(neighbours_ids) > 1:
                neighbours_ids.sort()
            nr_of_neighbours = len(neighbours_ids)
            my_poss_jacts = abs_possible_jacts[nr_of_neighbours]
            my_poss_jstates = []

            for neigh_id in neighbours_ids:
                my_poss_jstates.append(self.Lots[neigh_id].MaxStates)  # This is a list for each neigh

            mydict = self.Lots[i].CreateStateJActDict(self.Lots[i].MaxStates, self.AbsMaxActs, my_poss_jacts,
                                                      my_poss_jstates)
            dicts.append(mydict)

        return dicts

    # This function is from the book
    def GetJointAction(self, list_of_qtables, random_dilute_factor):
        rand_acts = [(random.randint(1, self.AbsMaxActs),) for k in
                     range(len(self.Lots))]  # Initialize rand actions for all agents
        ##### UP THERE THE INITIAL TUPLE IS A ONE ELEMENT TUPLE
        ##### UP HERE GET ABS_MAX_ACTIONS!

        # Dilute randomness via repetition
        for j in range(random_dilute_factor):
            # Iterate thourgh all agents and get action
            for i in range(len(self.Lots)):
                # First we get this agents neighbours
                agent_neighbours = self.IdNeigbours(self.Lots[i])

                # Then we get the action that the neighbours took (random initially)
                ag_neigh_acts = []
                for id in agent_neighbours:
                    ag_neigh_acts.append(rand_acts[id][0])  # on position 0 is the int, on 1 is the flag (str)

                ag_neigh_acts = tuple(ag_neigh_acts)  # convert to tuple, as the following function accepts a tuple

                # Then we use this joint neighbour actions to get our own
                agent_action = self.Lots[i].GetActionMulti(list_of_qtables[i], self.Lots[i].C_state,
                                                           self.Lots[i].Poss_act, EPSILON, ag_neigh_acts)

                # Then we replace our action on the initially random list of actions
                rand_acts[i] = agent_action

        return rand_acts  # This is a list of tuples with the actions and the flags corresponding to each agent

    # This function is from the code I downloaded
    def GetJointActions2(self, list_of_qtables, list_of_countvisits, combo_cstate):
        outacts = [0 for i in range(len(self.Lots))]  # an action for each agent

        for i in range(len(self.Lots)):
            outacts[i] = self.Lots[i].GetActionMulti2(EPSILON, list_of_qtables[i], list_of_countvisits[i],
                                                      combo_cstate[i])

        return outacts  # This returns a list of pairs, where first action, second flag

    # This function massively applies the actions to all the agents
    def TakeActions(self, list_of_actions):
        for i in range(len(list_of_actions)):
            self.Lots[i].Extend(list_of_actions[i][0])  # THIS IS EXPECTING A PAIR ACTION, FLAG

    # This function takes a list of q_tables (from sticky) as input
    def UpdateQTables(self, list_of_qtables, list_of_relevant_data, list_of_countvisits, current_jstates):
        RD_saves = [(None,) for j in range(len(list_of_qtables))]

        for i in range(len(self.Lots)):  # Iterate through the agents
            # Check if there is such as previous countdown
            checker = next(
                (dic for dic in list_of_relevant_data if dic['Countdown'] == COUNTDOWN + 1 and dic['Agent_Id'] == i),
                None)

            if not checker:
                # Get min (latest) countdown figure
                most_recent_ctdwn = min(dicts['Countdown'] for dicts in list_of_relevant_data)

                # Retrieve previous dictionary from list of dictionaries
                my_dic = next((dic for dic in list_of_relevant_data if
                               dic['Countdown'] == most_recent_ctdwn and dic['Agent_Id'] == i), None)

            else:
                my_dic = checker

            past_state = my_dic["State_0"]
            action = my_dic["Action"]
            joint_actions = my_dic["Joint_act"]

            if REWARD == GOAL_REWARD or REWARD == -GOAL_REWARD:
                new_qvalue = REWARD  # because reward alredy comes negative or positive
                RD_save = (new_qvalue,)
            else:
                # I need the values to calculate the q_table
                current_q = list_of_qtables[i][past_state][joint_actions][action]

                # Get future q
                future_q = self.Lots[i].GetMaxFutureQ(list_of_qtables[i], list_of_countvisits[i], current_jstates[i])

                # Get the new q_value
                new_qvalue = (1 - LEARNING_RATE) * current_q + LEARNING_RATE * (REWARD + DISCOUNT * future_q)
                RD_save = (new_qvalue, current_q, future_q)

            # Replace the q value on qtable
            list_of_qtables[i][past_state][joint_actions][action] = new_qvalue
            RD_saves[i] = RD_save

        # return a list of q_tables as the input but with updated q-values
        return [list_of_qtables, RD_saves]  # two lists

    # This function is like above, but takes elegibility traces dictionary (Watkins Q-lambda)
    def UpdateQTables2(self, list_of_qtables, list_of_relevant_data, list_of_countvisits, current_jstates,
                       list_elegibilityt, next_action_rand):
        RD_saves = [(None,) for j in range(len(list_of_qtables))]

        for i in range(len(self.Lots)):  # Iterate through the agents
            # Check if there is such as previous countdown
            checker = next(
                (dic for dic in list_of_relevant_data if dic['Countdown'] == COUNTDOWN + 1 and dic['Agent_Id'] == i),
                None)

            if not checker:
                # Get min (latest) countdown figure
                most_recent_ctdwn = min(dicts['Countdown'] for dicts in list_of_relevant_data)

                # Retrieve previous dictionary from list of dictionaries
                my_dic = next((dic for dic in list_of_relevant_data if
                               dic['Countdown'] == most_recent_ctdwn and dic['Agent_Id'] == i), None)

            else:
                my_dic = checker

            past_state = my_dic["State_0"]
            action = my_dic["Action"]
            joint_actions = my_dic["Joint_act"]

            # I need the values to calculate the q_table
            current_q = list_of_qtables[i][past_state][joint_actions][action]

            # Get future q # THIS IS USELES WHEN MAX_REWARD OR -MAX_REWARD, ALL ARE 0S!
            future_q = self.Lots[i].GetMaxFutureQ(list_of_qtables[i], list_of_countvisits[i], current_jstates[i])

            # Get the value of the new-qs formula that derives from present values
            from_current_state = (REWARD + (DISCOUNT * future_q)) - current_q

            # Turn tuple to string (joint actions)
            j_act_str = []
            for act in joint_actions:
                stt = str(act)
                j_act_str.append(stt)
            jactstr = '_'.join(j_act_str)

            # Get the identifier for the traces dictionary
            traces_id = past_state + ':' + jactstr + ':' + str(action)

            # if the identifier does not exist on elegibility dict, create
            if traces_id not in list_elegibilityt[i]:
                list_elegibilityt[i][traces_id] = 0.0

            # iterate through the dictionary and recover values visited
            for key, old_value in list_elegibilityt[i].items():
                trace_state, trace_jact, trace_act = key.split(":")
                # but only trace_state is a string (as in q_table dict)
                # trace_jact must go from str to tuple
                trace_jact = tuple(map(int, trace_jact.split('_')))

                # trace_act must go from str to int
                trace_act = int(trace_act)

                # Update the q-value and traces dictionary for currently visited state:jaction:action
                if past_state == trace_state and joint_actions == trace_jact and action == trace_act:
                    # Update traces dict
                    list_elegibilityt[i][key] = old_value + 1

                    # Update q_table
                    if REWARD == GOAL_REWARD or REWARD == -GOAL_REWARD:
                        list_of_qtables[i][past_state][joint_actions][action] = REWARD
                        RD_save = (REWARD,)
                    else:
                        new_q = current_q + LEARNING_RATE * list_elegibilityt[i][key] * from_current_state
                        list_of_qtables[i][past_state][joint_actions][action] = new_q
                        RD_save = (new_q, current_q, future_q)

                    # Save for relevant data
                    RD_saves[i] = RD_save

                    # Update the q-value dictionary for previously visited states
                else:
                    # Update q_table
                    old_qvalues = list_of_qtables[i][trace_state][trace_jact][trace_act]
                    new_qvalues = old_qvalues + LEARNING_RATE * list_elegibilityt[i][key] * from_current_state
                    list_of_qtables[i][trace_state][trace_jact][trace_act] = new_qvalues

                # Update traces dict as per Watkins Q-lambda
                if next_action_rand[
                    i] == False:  # if the next action is not random or does not exist (when max reward or penal)
                    list_elegibilityt[i][key] = DISCOUNT * TD_LAMBDA * old_value
                elif next_action_rand[i] == True:  # if next action is random, we cut off the traces
                    list_elegibilityt[i][key] = 0

        # return a list of q_tables as the input but with updated q-values
        return [list_of_qtables, RD_saves, list_elegibilityt]  # three lists

    # This function is like above but elegibility traces only on max goal!
    def UpdateQTables3(self, list_of_qtables, list_of_relevant_data, list_of_countvisits, current_jstates,
                       list_elegibilityt, next_action_rand):
        RD_saves = [(None,) for j in range(len(list_of_qtables))]

        for i in range(len(self.Lots)):  # Iterate through the agents
            # Check if there is such as previous countdown
            checker = next(
                (dic for dic in list_of_relevant_data if dic['Countdown'] == COUNTDOWN + 1 and dic['Agent_Id'] == i),
                None)

            if not checker:
                # Get min (latest) countdown figure
                most_recent_ctdwn = min(dicts['Countdown'] for dicts in list_of_relevant_data)

                # Retrieve previous dictionary from list of dictionaries
                my_dic = next((dic for dic in list_of_relevant_data if
                               dic['Countdown'] == most_recent_ctdwn and dic['Agent_Id'] == i), None)

            else:
                my_dic = checker

            past_state = my_dic["State_0"]
            action = my_dic["Action"]
            joint_actions = my_dic["Joint_act"]

            # I need the values to calculate the q_table
            current_q = list_of_qtables[i][past_state][joint_actions][action]

            # Get future q # THIS IS USELES WHEN MAX_REWARD OR -MAX_REWARD, ALL ARE 0S!
            future_q = self.Lots[i].GetMaxFutureQ(list_of_qtables[i], list_of_countvisits[i], current_jstates[i])

            # If we are not on goal reward, bussiness as usual
            if REWARD != GOAL_REWARD:
                new_qvalue = (1 - LEARNING_RATE) * current_q + LEARNING_RATE * (REWARD + DISCOUNT * future_q)
                RD_save = (new_qvalue, current_q, future_q)

                # Replace the q value on qtable
                list_of_qtables[i][past_state][joint_actions][action] = new_qvalue

                # Save on traces dictionary
                # Turn tuple to string (joint actions)
                j_act_str = []
                for act in joint_actions:
                    stt = str(act)
                    j_act_str.append(stt)
                jactstr = '_'.join(j_act_str)

                # Get the identifier for the traces dictionary
                traces_id = past_state + ':' + jactstr + ':' + str(action)

                # if the identifier does not exist on elegibility dict, create
                if traces_id not in list_elegibilityt[i]:
                    list_elegibilityt[i][traces_id] = 0.0

                # If it does exist, add a 1
                for key, old_value in list_elegibilityt[i].items():
                    trace_state, trace_jact, trace_act = key.split(":")
                    trace_jact = tuple(map(int, trace_jact.split('_')))

                    # trace_act must go from str to int
                    trace_act = int(trace_act)

                    # Update the q-value and traces dictionary for currently visited state:jaction:action
                    if past_state == trace_state and joint_actions == trace_jact and action == trace_act:
                        # Update traces dict
                        list_elegibilityt[i][key] = old_value + 1

            # If we are on goal reward
            else:
                list_of_qtables[i][past_state][joint_actions][action] = REWARD
                RD_save = (REWARD,)

                # Get the value of the new-qs formula that derives from present values
                from_current_state = (REWARD + (DISCOUNT * future_q)) - current_q

                # Update previous q_values
                for key, old_value in list_elegibilityt[i].items():
                    trace_state, trace_jact, trace_act = key.split(":")
                    trace_jact = tuple(map(int, trace_jact.split('_')))
                    trace_act = int(trace_act)

                    old_qvalues = list_of_qtables[i][trace_state][trace_jact][trace_act]
                    new_qvalues = old_qvalues + LEARNING_RATE * list_elegibilityt[i][key] * from_current_state
                    list_of_qtables[i][trace_state][trace_jact][trace_act] = new_qvalues

            RD_saves[i] = RD_save

        # return a list of q_tables as the input but with updated q-values
        return [list_of_qtables, RD_saves, list_elegibilityt]  # three lists

    # This function updates the relevant data dictionary (second version)
    def UpdateRelData1(self, list_of_actions, combo_cstate):
        list_of_dicts = []
        for i in range(len(self.Lots)):
            Current_state = combo_cstate[i]
            Action = list_of_actions[i][0]
            Flag = list_of_actions[i][1]

            neighbours_ids = self.IdNeigbours(i)
            Joint_act = []
            for id in neighbours_ids:
                ja = list_of_actions[id][0]
                Joint_act.append(ja)
            Joint_act = tuple(Joint_act)

            # Create a new dictionary
            my_dictone = {}

            my_dictone["Agent_Id"] = i
            my_dictone["Countdown"] = COUNTDOWN  # THIS IS THE ALTERED COUNTDOWN
            my_dictone["Episode"] = EPISODE
            my_dictone["Step"] = TIME_STEP
            my_dictone["State_0"] = Current_state
            my_dictone["Action"] = Action
            my_dictone["Joint_act"] = Joint_act
            my_dictone["Epsilon"] = EPSILON
            my_dictone["Flag"] = Flag

            list_of_dicts.append(my_dictone)

        return list_of_dicts  # return the input modifies accordingly. Upload to sticky!

    # This function updates the second part of the relevant data dictionary (second version)
    # q_factors = UpdateQTables(self, list_of_qtables, list_of_relevant_data)[1] # the 0 is the q-tables
    def UpdateRelData2(self, list_of_relevant_data, q_factors,
                       combo_cstate):  # Could get a list of calculated oldqs, max_future_qs and new_qs
        for i in range(len(self.Lots)):
            State_1 = combo_cstate[i]
            Remaining_Budget = BUDGET - (self.Lots[i].WallAreaExtCost + self.Lots[i].RoofAreaExtCost)
            Mod_occupied = self.Lots[i].NOccupiedPts
            # Check for q_factors
            if len(q_factors[i]) == 1:
                New_q = q_factors[i][0]
                old_q = None
                Max_future_q = None
            else:
                New_q = q_factors[i][0]
                old_q = q_factors[i][1]
                Max_future_q = q_factors[i][2]

            # Check if there is such as previous countdown
            checker = next(
                (dic for dic in list_of_relevant_data if dic['Countdown'] == COUNTDOWN + 1 and dic['Agent_Id'] == i),
                None)

            if not checker:
                # Get min (latest) countdown figure
                most_recent_ctdwn = min(dicts['Countdown'] for dicts in list_of_relevant_data)

                # Retrieve previous dictionary from list of dictionaries
                my_dic = next((dic for dic in list_of_relevant_data if
                               dic['Countdown'] == most_recent_ctdwn and dic['Agent_Id'] == i), None)

            else:
                my_dic = checker

            # Add data to that dictionary
            my_dic["Old_q"] = old_q
            my_dic["State_1"] = State_1
            my_dic["Reward"] = REWARD  # This is Universal!
            my_dic["Max_future_q"] = Max_future_q
            my_dic["New_q"] = New_q
            my_dic["Current_perf"] = CURRENT_PERF  # This is Universal!
            my_dic["Record_Perf"] = RECORD_PERF  # This is Universal!
            my_dic["Remaining_Budget"] = Remaining_Budget
            my_dic["LR"] = LEARNING_RATE
            my_dic["Mod_occupied"] = Mod_occupied

            # Replace dict on list of dicts by index
            list_of_relevant_data[list_of_relevant_data.index(my_dic)] = my_dic

        return list_of_relevant_data

    def UpdateStateJAVisits(self, list_of_prevSJA, list_of_relevant_data):
        for i in range(len(self.Lots)):
            # Check if there is such as previous countdown
            checker = next(
                (dic for dic in list_of_relevant_data if dic['Countdown'] == COUNTDOWN + 1 and dic['Agent_Id'] == i),
                None)

            if not checker:
                # Get min (latest) countdown figure
                most_recent_ctdwn = min(dicts['Countdown'] for dicts in list_of_relevant_data)

                # Retrieve previous dictionary from list of dictionaries
                my_dic = next((dic for dic in list_of_relevant_data if
                               dic['Countdown'] == most_recent_ctdwn and dic['Agent_Id'] == i), None)

            else:
                my_dic = checker

            state_0 = my_dic["State_0"]
            jact_0 = my_dic["Joint_act"]

            dict_prevSJA = list_of_prevSJA[i]

            dict_prevSJA[state_0][jact_0] += 1

            list_of_prevSJA[i] = dict_prevSJA

        return list_of_prevSJA

    # This function checks if the q_tables and SJA_dicts have the current joint state of each agent and updated them accordignly
    def CheckQtable(self, list_of_qtables, list_of_SJA_dicts, list_of_jstates, list_of_possibleacts):
        new_list_of_qtabs = []
        new_list_of_SJA = []
        for i in range(len(self.Lots)):
            my_jstate = list_of_jstates[i]  # current joint state for this agent
            my_qtab = list_of_qtables[i]  # current qtable for this agent
            my_SJA = list_of_SJA_dicts[i]  # Current count state-joint-action dictionary

            if my_jstate not in my_qtab:  # Check if the q_table has the current state
                my_possible_acts = list_of_possibleacts[i]

                neighbours_ids = self.IdNeigbours(i)
                neighbours_ids.sort()
                my_neighs_possacts = []
                for id in neighbours_ids:
                    neigh_possact = list_of_possibleacts[id]
                    my_neighs_possacts.append(neigh_possact)

                possible_neigh = []
                for max_acts in my_neighs_possacts:
                    acts = [i for i in range(max_acts + 2)]
                    possible_neigh.append(acts)

                combos = list(itertools.product(*possible_neigh))

                # If not, append a key with the new state
                my_qtab[my_jstate] = {}
                # We can assume it does not exist on the SJA dict either, so add as well
                my_SJA[my_jstate] = {}

                for combo in combos:
                    my_qtab[my_jstate][combo] = [0 for k in range(0, my_possible_acts + 2)]
                    my_SJA[my_jstate][combo] = 0

            new_list_of_qtabs.append(my_qtab)
            new_list_of_SJA.append(my_SJA)

        return [new_list_of_qtabs, new_list_of_SJA]


##### Construct brep #####
# Must add a Budget as input! so each agent has its own budget and space needs.
class HHagent:
    ' The agent can only construct growable modules on positive coordinates '

    # Initializer with plot location
    def __init__(self, lotorigx, lotorigy, lotsizex, lotsizey, module, coreorigx, coreorigy, coresizex, coresizey, maxh,
                 space_needed, walls_c, roof_c):
        self.MaxHeightFl = maxh
        self.LotOrigX = lotorigx
        self.LotOrigY = lotorigy
        self.WCost = walls_c
        self.RCost = roof_c

        if lotsizex <= 0:
            print ("lot size x must be greater than 0")
            self.LotSizeX = None
        else:
            self.LotSizeX = lotsizex
        if lotsizey <= 0:
            print ("lot size y must be greater than 0")
            self.LotSizeY = None
        else:
            self.LotSizeY = lotsizey

        self.Module = module

        # Accept only positive coordinates
        if coreorigx < 0:
            self.CoreOrigX = 0
        else:
            self.CoreOrigX = coreorigx

        if coreorigy < 0:
            self.CoreOrigY = 0
        else:
            self.CoreOrigY = coreorigy

        # The construction must be smaller than the lot
        if coresizex >= self.LotSizeX:
            self.CoreSizeX = self.LotSizeX
        elif coresizex < 1:
            self.CoreSizeX = 1
        else:
            self.CoreSizeX = coresizex

        if coresizey >= self.LotSizeY:
            self.CoreSizeY = self.LotSizeY
        elif coresizey < 1:
            self.CoreSizeY = 1
        else:
            self.CoreSizeY = coresizey

        self.CentreModulePts = self.TestPtsSt()
        self.VertixLots = self.vertix(self.LotOrigX, self.LotOrigY, self.LotSizeX, self.LotSizeY, self.Module)
        self.CoreOrigPt = self.coreorig(self.LotOrigX, self.LotOrigY, self.LotSizeX, self.LotSizeY, self.Module,
                                        self.CoreOrigX, self.CoreOrigY, self.CoreSizeX, self.CoreSizeY)
        self.VertixCore = self.vertix2(self.CoreOrigPt, self.CoreSizeX, self.CoreSizeY, self.Module)
        self.BrepCore = self.startingbrep(self.VertixCore)  # Keep in memory to retrieve

        self.InitInsidePt = self.InsidePts(self.BrepCore)[0]
        self.InitInsidePtIdx = self.InsidePts(self.BrepCore)[1]
        self.InitState = self.GetStateString(self.InitInsidePtIdx)
        self.MaxStates = self.FutStatesStr(space_needed)  # space needed is an input
        self.MyQTable = self.CreateQTable(self.MaxStates, self.MaxActions())

        # On initial stage
        self.OutBrep = self.BrepCore
        self.C_state = self.InitState
        self.Poss_act = self.AvailActs(self.OutBrep)
        self.NOccupiedPts = len(self.InsidePts(self.BrepCore)[0])
        self.WallAreaExtCost = 0  # as we havent extended
        self.RoofAreaExtCost = 0  # as we havent extended

    # Returns the points inside the voxels to test the state of the brep
    def TestPtsSt(self):
        first_pt = Rhino.Geometry.Point3d(self.LotOrigX + self.Module / 2, self.LotOrigY + self.Module / 2, self.Module / 2)

        pt_cloud = []

        for i in range(int(self.LotSizeX)):
            for j in range(int(self.LotSizeY)):
                for k in range(int(self.MaxHeightFl)):
                    pt = Rhino.Geometry.Point3d(first_pt.X + self.Module * i, first_pt.Y + self.Module * j,
                                    first_pt.Z + self.Module * k)
                    pt_cloud.append(pt)

        return pt_cloud

        # Find the index of the points inside the brep

    def InsidePts(self, brep):
        p_cloud = self.TestPtsSt()
        pts_inside = []
        index_inside = []
        for point in p_cloud:
            bol = brep.IsPointInside(point, Rhino.RhinoMath.SqrtEpsilon, False)
            if bol:
                pts_inside.append(point)
                index_inside.append(p_cloud.index(point))

        return (pts_inside, index_inside)

    # Find the index of the points that can be possibly occupied on the next stage
    def PossPointsIndex(self, brep):
        p_cloud = self.TestPtsSt()
        pts_inside = self.InsidePts(brep)[0]
        index_inside = self.InsidePts(brep)[1]

        index_of_possible = []
        for pts in pts_inside:
            for pt in p_cloud:
                if pts.DistanceTo(pt) == self.Module:
                    index_of_possible.append(p_cloud.index(pt))

        # Delete duplicates
        index_of_possible = list(dict.fromkeys(index_of_possible))

        # Delete indices of the ones initially inside the brep
        ind_possible = list(set(index_of_possible) - set(index_inside))

        return ind_possible

    # Does the same as above but the input is a list of indices inside an initial brep
    def PossPointsIndex2(self, inside_idx):
        p_cloud = self.TestPtsSt()
        pts_inside = []

        for idx in inside_idx:
            pt = p_cloud[idx]
            pts_inside.append(pt)

        index_of_possible = []
        for pts in pts_inside:
            for pt in p_cloud:
                if pts.DistanceTo(pt) == self.Module:
                    index_of_possible.append(p_cloud.index(pt))

        # Delete duplicates
        index_of_possible = list(dict.fromkeys(index_of_possible))

        # Delete indices of the ones initially inside the brep
        ind_possible = list(set(index_of_possible) - set(inside_idx))

        return ind_possible

        # Get possible index-states from a list of index inside brep and possible extension indeces

    def GetPossIdxStates(self, idxinsidelist, possibleidxlist):
        possibilities = []

        for ind in possibleidxlist:
            poss = idxinsidelist + [ind]  # Is only adding one each time
            possibilities.append(poss)

        return possibilities  # This is a list of lists

    # Get null state
    def GetNullState(self):
        times_mult = int(round(self.LotSizeX * self.LotSizeY * self.MaxHeightFl))
        str_to_mult = "F"
        comp_str = str_to_mult * times_mult

        return comp_str

    def MultipleGenSt(self, inital_idx, nrofgens):
        poss_idx = self.PossPointsIndex2(inital_idx)  # gets generation 1 of possible expansion
        gen1 = self.GetPossIdxStates(inital_idx, poss_idx)  # combinations including the original state
        all_gens = []  # ordered in sublists by generation (3 levels)
        all_gens.append(inital_idx)  # Generation 0 or initial input
        all_gens.append(gen1)  # First generation, first transformation
        all_gens_flattened = []  # just the lists of possible indices (2 levels)
        for i in gen1:
            all_gens_flattened.append(i)
        for gen in range(nrofgens - 2):
            this_gen = []
            for state in all_gens[-1]:
                poss_exp = self.PossPointsIndex2(
                    state)  # Visit each point originally occupied and project to possible next extensions
                nex_gen = self.GetPossIdxStates(state,
                                                poss_exp)  # possible comninations of indeces possible occupied on next generation
                for sublst in nex_gen:
                    this_gen.append(sublst)
            this_gen = RemoveSubL(this_gen)  # Delete duplicated sublists
            all_gens.append(this_gen)  # append whole generation for next iteration
            for i in this_gen:  # Append only idx of possible states
                all_gens_flattened.append(i)

        all_gens_flattened = RemoveSubL(all_gens_flattened)  # Remove duplicated sub-lists
        return all_gens_flattened  # This is a 2 level list

    # From index of points to a valid state string
    def GetStateString(self, indlist):
        NullState = self.GetNullState()
        list_str = list(NullState)

        for ind in indlist:
            list_str[ind] = "T"

        out_str = "".join(list_str)
        return out_str

    # Get possible next states from pre-defined initial state
    def FutStatesStr(self, generations):
        idx_next_mods = self.MultipleGenSt(self.InitInsidePtIdx,
                                           int(generations))  # For the said number of generations
        Poss_st = []  # List of strings with the possible future states

        # From index to string
        for idx in idx_next_mods:
            Poss_st.append(self.GetStateString(idx))

        # Check for possible duplicates
        Poss_st = list(dict.fromkeys(Poss_st))

        # Append the initial state
        Poss_st.append(self.InitState)

        return Poss_st

    # Forms four vertices from coordinates of origin and size
    def vertix(self, xorig, yorig, xsize, ysize, module):
        lot1 = Rhino.Geometry.Point3d(xorig, yorig, 0)
        lot2 = Rhino.Geometry.Point3d(xorig + (xsize * module), yorig, 0)
        lot3 = Rhino.Geometry.Point3d(xorig + (xsize * module), yorig + (ysize * module), 0)
        lot4 = Rhino.Geometry.Point3d(xorig, yorig + (ysize * module), 0)
        lot5 = Rhino.Geometry.Point3d(xorig, yorig, 0)

        lotverts = [lot1, lot2, lot3, lot4, lot5]
        return lotverts

    # Returns a point with relative coordinates within a lot
    def coreorig(self, lotorigx, lotorigy, lotsizex, lotsizey, module, coreorigx, coreorigy, coresizex, coresizey):
        x3abs = lotorigx + (coreorigx * module)  # when x3 == module, does not work!
        y3abs = lotorigy + (coreorigy * module)  # when y3 == module, does not work!

        if x3abs >= lotorigx + (lotsizex * module) - (coresizex * module):
            absx = (lotorigx + (lotsizex * module)) - (coresizex * module)
        elif x3abs < lotorigx:
            absx = lotorigx + (coresizex * module)
        else:
            absx = x3abs

        if y3abs >= lotorigy + (lotsizey * module) - (coresizex * module):
            absy = (lotorigy + (lotsizey * module)) - (coresizey * module)
        elif y3abs < lotorigy:
            absy = lotorigy + (coresizey * module)
        else:
            absy = y3abs

        coreorig = Rhino.Geometry.Point3d(absx, absy, 0)
        return coreorig

    # Same as vertix() but with fewer inputs
    def vertix2(self, coreorigpt, coresizex, coresizey, module):
        unop = Rhino.Geometry.Point3d(coreorigpt.X, coreorigpt.Y, coreorigpt.Z)
        dosp = Rhino.Geometry.Point3d(coreorigpt.X + (coresizex * module), coreorigpt.Y, 0)
        tresp = Rhino.Geometry.Point3d(coreorigpt.X + (coresizex * module), coreorigpt.Y + (coresizey * module), 0)
        cuatrop = Rhino.Geometry.Point3d(coreorigpt.X, coreorigpt.Y + (coresizey * module), 0)
        cincop = Rhino.Geometry.Point3d(coreorigpt.X, coreorigpt.Y, coreorigpt.Z)

        points = System.Collections.Generic.List[Rhino.Geometry.Point3d]()
        points.Add(unop)
        points.Add(dosp)
        points.Add(tresp)
        points.Add(cuatrop)
        points.Add(cincop)
        return points

    # Create a Brep for the initial core (This creates a brep with 6 faces)
    def startingbrep(self, fourpts):
        polyl = Rhino.Geometry.Polyline(fourpts)  # create a polyline with four pts
        polyc = polyl.ToPolylineCurve()  # Transform to Polyline curve
        basesurf = Rhino.Geometry.Brep.CreatePlanarBreps(polyc, 0.1)  # Transform to planar brep
        initialp = fourpts[0]  # Initial input point
        curvextr = Rhino.Geometry.LineCurve(initialp, Rhino.Geometry.Point3d(initialp.X, initialp.Y, self.Module))  # Line to guide extrusion
        outbrep = Rhino.Geometry.BrepFace.CreateExtrusion(basesurf[0].Faces[0], curvextr, cap=True)  # Extrude planar brep

        orientation = outbrep.SolidOrientation

        if orientation == Rhino.Geometry.BrepSolidOrientation.Inward:  # Brep is a Solid with inward facing normals
            outbrep.Flip()

        return outbrep

    def startingstate(self):
        p_cloud = self.TestPtsSt()
        list_of_bool = []

        for point in p_cloud:
            bol = self.BrepCore.IsPointInside(point, Rhino.RhinoMath.SqrtEpsilon, False)
            list_of_bool.append(bol)

        my_bolstr_list = []
        for bol in list_of_bool:
            if bol:
                st = "T"
                my_bolstr_list.append(st)
            else:
                st = "F"
                my_bolstr_list.append(st)

        c_state = ''.join(my_bolstr_list)

        return c_state

    # Classify vertices in sublists according to the index of the face they belong to
    def ClassifyVertix(self, inbrep):
        faces = inbrep.Faces
        edg = inbrep.Edges

        edgeindex = [[] for i in range(faces.Count)]  # Edges indices grouped by the face they belong to
        vertices = [[] for i in range(faces.Count)]  # Star an ending points by surface they belong to

        for face in faces:
            edges = face.AdjacentEdges()
            for index in edges:
                edgeindex[face.FaceIndex].append(index)

        for surface in edgeindex:
            for index in surface:
                edge = edg[index]
                startpt = edge.PointAtStart
                endpt = edge.PointAtEnd
                vertices[edgeindex.index(surface)].append(startpt)
                vertices[edgeindex.index(surface)].append(endpt)

        # First must clean each of the subgroups inside vertices, so no repeated points are left
        for i in range(len(vertices)):
            vertices[i] = list(dict.fromkeys(vertices[i]))

        return vertices

    # Classify index in walls, roof and floor
    def ClassifyFaces(self, inbrep):
        vertices = self.ClassifyVertix(inbrep)

        roofs = []
        wandr = []
        walls_up = []

        walls = []
        floor = []

        for faceindex in vertices:
            zs = []
            for vertex in faceindex:
                if vertex.Z == 0:
                    zs.append(vertex)
            if len(zs) == 2:
                walls.append(vertices.index(faceindex))
            if len(zs) == 4:
                floor.append(vertices.index(faceindex))
            if len(zs) == 0:
                wandr.append(vertices.index(faceindex))

        for indexn in wandr:
            zs = []
            for vertix in vertices[indexn]:
                zs.append(vertix.Z)

            # If all zs within the list are the same
            if all(x == zs[0] for x in zs) == True:
                roofs.append(indexn)
            else:  # Others are walls from upper floors
                walls_up.append(indexn)

        return [walls, roofs, floor, walls_up]

    def WallsAreasExtension(self, initialbrep, finalbrep):
        classed_init = list(set(self.ClassifyFaces(initialbrep)[0] + self.ClassifyFaces(initialbrep)[3]))
        classed_end = list(set(self.ClassifyFaces(finalbrep)[0] + self.ClassifyFaces(finalbrep)[3]))

        my_areas_init = []
        my_areas_end = []

        for idx in classed_init:
            srf_brp = initialbrep.Faces[idx].ToBrep()
            my_area = srf_brp.GetArea()
            my_areas_init.append(my_area)

        for idx in classed_end:
            srf_brp = finalbrep.Faces[idx].ToBrep()
            my_area = srf_brp.GetArea()
            my_areas_end.append(my_area)

        walls_area_init = sum(my_areas_init)
        walls_area_end = sum(my_areas_end)

        extension_wall_a = int(round(walls_area_end - walls_area_init))

        return extension_wall_a

    def RoofsAreasExtension(self, initialbrep, finalbrep):
        classed_init = self.ClassifyFaces(initialbrep)[1]
        classed_end = self.ClassifyFaces(finalbrep)[1]

        my_areas_init = []
        my_areas_end = []

        for idx in classed_init:
            srf_brp = initialbrep.Faces[idx].ToBrep()
            my_area = srf_brp.GetArea()
            my_areas_init.append(my_area)

        for idx in classed_end:
            srf_brp = finalbrep.Faces[idx].ToBrep()
            my_area = srf_brp.GetArea()
            my_areas_end.append(my_area)

        roofs_area_init = sum(my_areas_init)
        roofs_area_end = sum(my_areas_end)

        extension_roof_a = int(round(roofs_area_end - roofs_area_init))

        return extension_roof_a

    # Filter the index of the walls that are on a plot boundary (cannot extend)
    def FilterWalls(self, inbrep):
        vertices = self.ClassifyVertix(inbrep)

        # Set the size of the lot
        minx = self.LotOrigX
        miny = self.LotOrigY
        maxx = self.LotOrigX + (self.LotSizeX * self.Module)
        maxy = self.LotOrigY + (self.LotSizeY * self.Module)

        # Select the index of the faces that are on borders (cannot grow)
        FacesOnBorders = []

        for faceindex in vertices:
            OnMinXBorder = []
            OnMinYBorder = []
            OnMaxXBorder = []
            OnMaxYBorder = []
            for pt in faceindex:
                if abs(pt.X - minx) < 0.0001:
                    OnMinXBorder.append(pt)
                if abs(pt.X - maxx) < 0.0001:
                    OnMaxXBorder.append(pt)
                if abs(pt.Y - miny) < 0.0001:
                    OnMinYBorder.append(pt)
                if abs(pt.Y - maxy) < 0.0001:
                    OnMaxYBorder.append(pt)

            if len(OnMinXBorder) == 4 or len(OnMinYBorder) == 4 or len(OnMaxXBorder) == 4 or len(OnMaxYBorder) == 4:
                FacesOnBorders.append(vertices.index(faceindex))

        # Compare index of faces on borders with walls, and delete walls on borders
        walls = self.ClassifyFaces(inbrep)[0]
        if len(FacesOnBorders) > 0:
            for i in FacesOnBorders:
                for j in walls:
                    if i == j:
                        walls.remove(j)

        return walls

    # Filter the roofs so only those under the max height are elegible to grow
    def FilterRoofs(self, inbrep):
        vertices = self.ClassifyVertix(inbrep)

        # Select the index of the faces that cannot grow
        FacesOnTop = []

        for faceindex in vertices:
            OntopZ = []
            for pt in faceindex:
                if pt.Z >= self.MaxHeightFl * self.Module:
                    OntopZ.append(pt)
            if len(OntopZ) == 4:
                FacesOnTop.append(vertices.index(faceindex))

        # Compare index of roofs on maxheight with roofs, and delete roofs on maxheight
        roofs = self.ClassifyFaces(inbrep)[1]
        if len(FacesOnTop) > 0:
            for i in FacesOnTop:
                for j in roofs:
                    if i == j:
                        roofs.remove(j)

        return roofs

    # Return number of available actions at the current state
    def AvailActs(self, inbrep):
        walls = self.FilterWalls(inbrep)
        roofs = self.FilterRoofs(inbrep)
        availopts = len(walls) + len(roofs)  # When we run out of options this sum is 0

        return availopts

    # reconvert input action to available number of growable surfaces
    def BoundInputAction(self, action, inbrep):
        availopts = self.AvailActs(inbrep)
        INaction = int(action)

        if availopts > 0:
            if -1 <= INaction <= availopts:
            #if -1 <= INaction < availopts:
                OUTaction = INaction
            elif INaction >= availopts and INaction % availopts == 0:
                OUTaction = availopts
            elif INaction >= availopts and INaction % availopts != 0:
                OUTaction = INaction % availopts
            elif INaction < -1:
                OUTaction = -1
        else:
            if INaction <= -1:
                OUTaction = -1
            else:
                OUTaction = 0  # If we run out of options, do nothing
                print ("Max growth achieved")

        return OUTaction

        # Keep the same order of actions so everytime we hit a state, an action leads to the same future state

    def OrderActions(self, inbrep, tolerance):
        AllPts = self.CentreModulePts
        IdxptsInside = self.InsidePts(inbrep)[1]
        IdxptsInside.sort()
        available = self.FilterWalls(inbrep) + self.FilterRoofs(inbrep)

        brepFaces = inbrep.Faces

        all_faces = []

        for idx in IdxptsInside:
            pt = AllPts[idx]
            close_faces = []
            for face in brepFaces:
                if face.FaceIndex in available:  # Check if in growable faces
                    facepts = face.ClosestPoint(pt)
                    pt3d = face.PointAt(facepts[1], facepts[2])
                    if pt3d.DistanceTo(pt) <= self.Module / 2 + tolerance:
                        close_faces.append(face.FaceIndex)
                    for faceidx in close_faces:
                        all_faces.append((idx, faceidx))

        all_faces = list(dict.fromkeys(all_faces))  # Delete duplicates
        all_faces.sort()  # Sort list in increasing order
        return all_faces

    # Output vectors
    def VectorExt(self, action, inbrep):
        OUTaction = self.BoundInputAction(action, inbrep)
        walls = self.FilterWalls(inbrep)  # indices of BREP faces that are walls
        roofs = self.FilterRoofs(inbrep)
        # roofs = self.ClassifyFaces(inbrep)[1] # indices of BREP faces that are roof
        floor = self.ClassifyFaces(inbrep)[2]  # indices of BREP faces that are floo

        allfaces = inbrep.Faces

        allvertices = self.ClassifyVertix(inbrep)  # all BREP vertices ordered in subgroups according to face index

        # Get face according to ordered list
        ordered_idx = self.OrderActions(inbrep, 0.05)

        idxFace2move = ordered_idx[OUTaction - 1][1]  # Face to move

        # if it is wall, get outward looking vector
        if idxFace2move in walls:
            # movingface = allfaces[walls[OUTaction - 1]]
            movingface = allfaces[idxFace2move]

            # Get index of adjacent faces
            adjacentfaces = movingface.AdjacentFaces()

            # Which of the adjacent are floors?
            adjacentfloor = list(set(adjacentfaces).intersection(floor))

            # Get the vertices of that face
            floorvertix = allvertices[adjacentfloor[0]]
            
            # Convert python list to system collection
            flvert = System.Collections.Generic.List[Rhino.Geometry.Point3d]()

            for apt in floorvertix:
                flvert.Add(apt)
            
            # Duplicate first point to last (to close the polyline)            
            lastpt = Rhino.Geometry.Point3d(floorvertix[0])
            flvert.Add(lastpt)

            # Form a closed polyline with them
            PolyL = Rhino.Geometry.Polyline(flvert)

            # Get the centre point of the polyline
            cpoint = PolyL.CenterPoint()

            # Get the vertices of the face to be moved (movingface)
            # movevertices = allvertices[walls[OUTaction - 1]]
            movevertices = allvertices[idxFace2move]

            # Select the two point whose z = 0
            ptsbase0 = []
            for vertex in movevertices:
                if vertex.Z == 0:
                    ptsbase0.append(vertex)

            # Draw a line between these two points
            line = Rhino.Geometry.Line(ptsbase0[0], ptsbase0[1])

            # Project centre pt on ab
            cprima = line.ClosestPoint(cpoint, False)

            # Build a vector between points
            dif = cprima - cpoint

            # Lenght of vector = 1
            dif.Unitize()

            # Multiply vector for module
            dif = dif * self.Module

            # Displace one of the points of the wall by vector
            initialp = Rhino.Geometry.Point3d(ptsbase0[0])
            finalp = Rhino.Geometry.Point3d(ptsbase0[0])
            finalp.Transform(Rhino.Geometry.Transform.Translation(dif))

            # Form a curve with original and displaced point
            curvextr = Rhino.Geometry.LineCurve(initialp, finalp)

            return curvextr

            # if it is roof get upward looking vector
        if idxFace2move in roofs:
            movingface = allfaces[idxFace2move]

            # Get one vertex from the moving face
            initialpts = allvertices[idxFace2move]
            initialp = Rhino.Geometry.Point3d(initialpts[0])

            # Create another with the same x & y but z = current z + module
            finalp = Rhino.Geometry.Point3d(initialp.X, initialp.Y, initialp.Z + self.Module)

            # Create a curve between this two points
            curvextr = Rhino.Geometry.LineCurve(initialp, finalp)

            return curvextr

        # What happens when the OutAction is beyond the avail number of faces?

    # Identify duplicated faces
    def IdDuplicated(self, inbrep):
        vertices = self.ClassifyVertix(inbrep)
        cpts = []
        repeatedi = []

        for vertixlist in vertices:
            vertixlist.append(Rhino.Geometry.Point3d(vertixlist[0]))
            
            # Convert python list to system collection
            vtrxlt = System.Collections.Generic.List[Rhino.Geometry.Point3d]()
            
            for itt in vertixlist:
                vtrxlt.Add(itt)
                
            polyl = Rhino.Geometry.Polyline(vtrxlt)
            cpt = polyl.CenterPoint()
            cpt = Rhino.Geometry.Point3f(cpt.X, cpt.Y, cpt.Z)
            cpts.append(cpt)

        for i in range(len(cpts)):
            for j in range(len(cpts)):
                if i != j and cpts[i].DistanceTo(cpts[j]) < 0.0001:
                    repeatedi.append(i)

        return repeatedi

    ##### Functions needed for q-learning #####

    def CreateQTable(self, max_states, max_acts):
        my_qtable = {}
        n_state = self.GetNullState()
        max_states.append(n_state)
        # When performance as state
        for state_s in max_states:
            my_qtable[state_s] = [random.uniform(-1, 0) for k in range(0, max_acts + 2)]
            #sc.sticky["q_tab_mem"] = my_qtable

        return my_qtable

    ####### HERE MAX_ACTS MUST BE THE ABSOLUTE MAXIMUM FOR ALL THE AGENTS!
    # Creates a q-table considering all possible joint actions and joint states
    def CreateMultiQTable(self, max_states, max_acts, possible_jacts, possible_jstates):
        my_qtable = {}

        # Append null state to the list of my possible states
        n_state = self.GetNullState()
        max_states.append(n_state)

        # Append null state to the list of my neighbours possible states
        for possible_neighst in possible_jstates:
            possible_neighst.append(n_state)

        # Convert possible combos to strings
        for l in possible_jstates:
            first_g = list(itertools.product(max_states, l))  # List of tuples with two strings
            temp_list = []
            for tup in first_g:
                stri = '_'.join(tup)  # Join the two string on the tuple
                temp_list.append(stri)  # append joined str to temporary list
            max_states = temp_list  # replace initial list for list of joined tuples

        # Now max_states is a list of joined str of all possible combos
        for state_s in max_states:
            my_qtable[state_s] = {}
            for tup in possible_jacts:
                my_qtable[state_s][tup] = [0 for k in range(0,
                                                            max_acts + 2)]  # THIS ACCORDING TO THE NEW ACTION SELECTION ALGORITHM

        return my_qtable

    def CreateStateJActDict(self, poss_states, max_acts, poss_jacts, possible_jstates):
        mydict = {}
        n_state = self.GetNullState()
        poss_states.append(n_state)

        # Append null state to the list of my neighbours possible states
        for possible_neighst in possible_jstates:
            possible_neighst.append(n_state)

        # Convert possible combos to strings
        for l in possible_jstates:
            first_g = list(itertools.product(poss_states, l))  # List of tuples with two strings
            temp_list = []
            for tup in first_g:
                stri = '_'.join(tup)  # Join the two string on the tuple
                temp_list.append(stri)  # append joined str to temporary list
            poss_states = temp_list  # replace initial list for list of joined tuples

        for state_s in poss_states:
            mydict[state_s] = {}
            for tup in poss_jacts:
                mydict[state_s][tup] = 0

        return mydict

    # Dictionary with relevant data (OLD VERSION)
    def CreateGDict(self, max_steps, max_episodes, columns):
        relevant_dat_now = {}
        columns = int(columns)
        for i in range(max_steps * max_episodes):
            relevant_dat_now[i] = [None for j in range(columns)]

        return relevant_dat_now

    # Dictionary with relevant data (NEW VERSION - DICTIONARY WITH NAMES)
    def CreateGDict2(self, max_steps, max_episodes):
        relevant_dat_now = {}
        data_fields = ["Countdown", "Episode", "Step", "State_0", "Action", "Joint_act", "Epsilon", "Flag", "Old_q",
                       "State_1", "Reward", "Max_future_q", "New_q", "Current_perf", "Record_Perf", "Remaining_Budget",
                       "LR", "Mod_occupied"]
        time_steps = max_steps * max_episodes
        for field in data_fields:
            relevant_dat_now[field] = [None for j in range(time_steps)]

        return relevant_dat_now

    def GetAction(self, q_tab, initial_state, possible_acts, epsi):
        if random.random() > epsi:
            qs_state = q_tab[initial_state]

            # Exclude action (index of list) = 0 and impossible actions
            to_exclude = {0}
            useless_actions = range(int(possible_acts), self.MaxActions() + 2)
            for on in useless_actions:
                to_exclude.add(on)
            vector2 = [element for i, element in enumerate(qs_state) if i not in to_exclude]
            action = qs_state.index(max(vector2))
            flag = "From Table"
        else:
            action = random.randint(1, int(possible_acts))
            flag = "Random"

        return [action, flag]

    # This function accepts a tuple as input for othersaction
    def GetActionMulti(self, q_tab, initial_state, possible_acts, epsi, othersaction):
        if random.random() > epsi:
            qs_state = q_tab[initial_state][othersaction]

            # Exclude action (index of list) = 0 and impossible actions
            to_exclude = {0}
            useless_actions = range(int(possible_acts), self.MaxActions() + 2)
            for on in useless_actions:
                to_exclude.add(on)
            vector2 = [element for i, element in enumerate(qs_state) if i not in to_exclude]
            action = qs_state.index(max(vector2))
            flag = "From Table"
        else:
            action = random.randint(1, int(possible_acts))
            flag = "Random"

        return (action, flag)

    # This function gets actions according to the code I downloaded
    # Allows inputing only EPSILON in case you need a fully random action
    def GetActionMulti2(self, epsi, q_tab=None, state_jaction_visited=None, current_jstate=None):
        ##### THE FOLLOWING SELECTS AN ACTION FROM ABS_MAX_ACTS! Therefore it might be inefficient
        ##### must find a way to limit this to only self.Poss_act as when random
        if random.random() > epsi:
            ### Get average q_values for current state ###
            # Get the total times visited this state
            state_visits = sum(state_jaction_visited[current_jstate].values())

            # list of available joint actions
            availjact = list(q_tab[current_jstate].keys())

            # list of available actions
            availacts = len(q_tab[current_jstate][availjact[0]])

            # Get dot product between q_table and times visited
            dot_product = [0 for i in range(availacts)]

            for my_action in range(availacts):  # This corresponds to my actions and are ints
                live_sum = 0
                for j_action in availjact:  # Possible j-action combos (tuples)
                    mult = (q_tab[current_jstate][j_action][my_action] * state_jaction_visited[current_jstate][
                        j_action]) + live_sum
                    live_sum = mult
                dot_product[my_action] = live_sum

            # If condition, get average
            if state_visits > 0:
                new_expectedq = [0 for i in range(len(dot_product))]
                for i in range(len(new_expectedq)):
                    new_expectedq[i] = dot_product[i] / state_visits
            else:
                new_expectedq = dot_product

            # Return indices that are non-zero
            flatenzero = []
            for expected in new_expectedq:
                # Get all the indices of elements that are not zero EXCEPT if the max is zero, if so, return the index of the max
                if expected != 0 and expected == max(new_expectedq):
                    flatenzero.append(new_expectedq.index(expected))
            if len(flatenzero) < 1:
                flatenzero.append(new_expectedq.index(max(new_expectedq)))

            # Get action
            action = random.choice(flatenzero)
            flag = "From Table"

        else:
            action = random.randint(1, int(self.Poss_act))
            flag = "Random"

        return (action, flag)

    def GetMaxFutureQ(self, q_tab, state_jaction_visited, current_jstate):
        # Get the total times visited this state
        state_visits = sum(state_jaction_visited[current_jstate].values())

        # list of available joint actions
        availjact = list(q_tab[current_jstate].keys())

        # list of available actions
        availacts = len(q_tab[current_jstate][availjact[0]])  # This is a int

        # Get dot product between q_table and times visited
        dot_product = [0 for i in range(availacts)]

        for my_fut_action in range(availacts):
            live_sum = 0
            for j_action in availjact:  # Possible j-action combos (tuples) MAYBE JUST GET ALL THE KEYS OF THE DICT!
                mult = (q_tab[current_jstate][j_action][my_fut_action] * state_jaction_visited[current_jstate][
                    j_action]) + live_sum
                live_sum = mult
            dot_product[my_fut_action] = live_sum

            # If condition, get average
        if state_visits > 0:
            new_expectedq = [0 for i in range(len(dot_product))]
            for i in range(len(new_expectedq)):
                new_expectedq[i] = dot_product[i] / state_visits
        else:
            new_expectedq = dot_product

        # return the max expected q-value
        filter_zeros = list(filter(lambda x: x != 0, new_expectedq))  # This is the q_values without 0s

        # If there are only 0s, expected q is 0
        if len(filter_zeros) < 1:
            max_future_q = 0
        else:
            max_future_q = max(filter_zeros)  # Or if I choose the action in advance
        # the index corresponding to the action

        return max_future_q

    def MaxActions(self):
        # Estimate the maximun number of possible actions at the same time-step
        if self.LotSizeX == 1:
            maxopt = self.LotSizeY
        elif self.LotSizeY == 1:
            maxopt = self.LotSizeX
        else:
            # This formula calculate the max number of actions in a single state transition
            # considering only one possible transformation per face per episode
            maxopt = self.LotSizeY + (((self.LotSizeY * 2) - 1) * (self.LotSizeX - 1))

        return int(round(maxopt))  # the max number of possible actions

    # Mult factor if you want to create a single dictionary for many agents of the same size
    def GetRecordDict(self, mult_factor=1):
        max_pts_occupied = self.LotSizeX * self.LotSizeY * self.MaxHeightFl

        # The range of possibly occupied points on a single step
        poss_pts = [i for i in range(int(max_pts_occupied) * mult_factor + 1)]
        my_dict = {}

        # There is one record per area
        for pts in poss_pts:
            my_dict[pts] = 0

        return my_dict

    ##### Function to extend #####

    # Extrude face of BREP with vector resulting from previous step
    def Extend(self, action):
        # If sticky of the brep does not exist yet, upload brep.Core
        # if not sc.sticky.has_key("brep_mem") or sc.sticky["brep_mem"] == None:
        # sc.sticky["brep_mem"] = self.BrepCore

        if action <= -1:
            # Here should be enough with deleting the next line
            # sc.sticky["brep_mem"] = self.BrepCore # save core to memory
            self.OutBrep = self.BrepCore  # This will not work when input external BREP

            # Inform about the current state
            p_cloud = self.TestPtsSt()
            list_of_bool = []
            for point in p_cloud:
                bol = self.OutBrep.IsPointInside(point, Rhino.RhinoMath.SqrtEpsilon, False)
                list_of_bool.append(bol)

            my_bolstr_list = []
            for bol in list_of_bool:
                if bol:
                    st = "T"
                    my_bolstr_list.append(st)
                else:
                    st = "F"
                    my_bolstr_list.append(st)

            self.C_state = ''.join(my_bolstr_list)
            self.C_Area = int(round(self.BrepCore.GetArea()))
            self.Poss_act = self.AvailActs(self.OutBrep)

            # Calculate extension costs (as there is no extension, no cost)
            self.WallAreaExtCost = 0
            self.RoofAreaExtCost = 0

            # How many points is occupying the resulting BREP?
            self.NOccupiedPts = len(self.InsidePts(self.OutBrep)[0])

        elif action == 0:  # On 0, we keep the state
            # Inform about the current state
            p_cloud = self.TestPtsSt()
            list_of_bool = []
            for point in p_cloud:
                bol = self.OutBrep.IsPointInside(point, Rhino.RhinoMath.SqrtEpsilon, False)
                list_of_bool.append(bol)

            my_bolstr_list = []
            for bol in list_of_bool:
                if bol:
                    st = "T"
                    my_bolstr_list.append(st)
                else:
                    st = "F"
                    my_bolstr_list.append(st)

            self.C_state = ''.join(my_bolstr_list)
            self.C_Area = int(round(self.OutBrep.GetArea()))
            self.Poss_act = self.AvailActs(self.OutBrep)

            # Calculate extension costs
            extWallArea = self.WallsAreasExtension(self.BrepCore, self.OutBrep)
            extRoofArea = self.RoofsAreasExtension(self.BrepCore, self.OutBrep)
            self.WallAreaExtCost = extWallArea * float(self.WCost)
            self.RoofAreaExtCost = extRoofArea * float(self.RCost)

            # How many points is occupying the resulting BREP?
            self.NOccupiedPts = len(self.InsidePts(self.OutBrep)[0])

        else:
            # recover brep from memory
            # inbrep = sc.sticky["brep_mem"]
            inbrep = self.OutBrep

            outaction = self.BoundInputAction(action, inbrep)  # index of available faces

            # transform recovered brep
            availablefaces = self.FilterWalls(inbrep) + self.FilterRoofs(inbrep)

            # Get face to move
            insd_pts = self.InsidePts(inbrep)[1]

            ordered_idx = self.OrderActions(inbrep, 0.05)
            idxFace2move = ordered_idx[outaction - 1][1]  # Index of face to move
            facetomove = inbrep.Faces[idxFace2move]

            curve = self.VectorExt(action, inbrep)
            newbrep = facetomove.CreateExtrusion(curve, True)

            # Remove extruded face
            newbrep.Faces.RemoveAt(idxFace2move)

            # Remove duplicated faces
            dupindex = self.IdDuplicated(newbrep)

            if len(dupindex) > 0:
                for i in range(0, len(dupindex)):
                    newbrep.Faces.RemoveAt(dupindex[i] - i)

            # To get a closed Brep and thus point all faces outwards
            # Transform brep to mesh
            meshingparam = Rhino.Geometry.MeshingParameters()
            meshingparam.MinimumEdgeLength = self.Module - 0.01

            mymeshes = Rhino.Geometry.Mesh.CreateFromBrep(newbrep, meshingparam)
            mymesh = Rhino.Geometry.Mesh()
            for mesh in mymeshes:
                mymesh.Append(mesh)

            # Fill the holes in the mesh
            mymesh.FillHoles()
            mymesh.HealNakedEdges(0.001)

            # Check if mesh is closed
            #if mymesh.IsClosed:
                #print "Mesh is closed (b)"

            # Keep faces as quadrangles
            mymesh.Faces.ConvertTrianglesToQuads(0, 0)

            # Transform again to brep
            myOutmesh = Rhino.Geometry.Brep.CreateFromMesh(mymesh, True)

            if myOutmesh.SolidOrientation == Rhino.Geometry.BrepSolidOrientation.Inward:
                print ("Mesh is inward (b), Flipping!")
                myOutmesh.Flip()

            # Export closed brep for analysis
            self.OutBrep = myOutmesh

            # Inform about the current state
            p_cloud = self.TestPtsSt()
            list_of_bool = []
            for point in p_cloud:
                bol = self.OutBrep.IsPointInside(point, Rhino.RhinoMath.SqrtEpsilon, False)
                list_of_bool.append(bol)

            my_bolstr_list = []
            for bol in list_of_bool:
                if bol:
                    st = "T"
                    my_bolstr_list.append(st)
                else:
                    st = "F"
                    my_bolstr_list.append(st)

            self.C_state = ''.join(my_bolstr_list)
            self.C_Area = int(round(myOutmesh.GetArea()))
            self.Poss_act = self.AvailActs(self.OutBrep)

            # Calculate extension costs
            extWallArea = self.WallsAreasExtension(self.BrepCore, self.OutBrep)
            extRoofArea = self.RoofsAreasExtension(self.BrepCore, self.OutBrep)
            self.WallAreaExtCost = extWallArea * float(self.WCost)
            self.RoofAreaExtCost = extRoofArea * float(self.RCost)

            # How many points is occupying the resulting BREP?
            self.NOccupiedPts = len(self.InsidePts(self.OutBrep)[0])