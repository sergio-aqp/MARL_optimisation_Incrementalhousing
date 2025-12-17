The main programme is on MARL_cloud.py

final_soc_mod.csv is in example of input file coming from the socio-economic model

Previous to running the programme you need to have installed in your computer:
- A licensed version of Rhino 7
- OpenStudio 3.4.0
- Ladybug Tools 1.5.0 (https://www.food4rhino.com/en/app/ladybug-tools)
- Python 3.7.9

Then you need to install the following packages in your working python environment:
- pip install -U honeybee-energy[standards]==1.95.21
- pip install rhinoinside==0.6.0
- pip install pollination-streamlit==0.5.0
- pip install Rhino==0.0.5
- pip install honeybee-radiance==1.64.107

The following packages must be installed without dependencies to avoid conflict
- pip install ladybug-rhino===1.38.1 --no-deps
- pip install lbt-recipes==0.23.0 --no-deps

The simulation on the cloud might not work due to changes in Pollination server. To allow execution, the token input must be edited.
