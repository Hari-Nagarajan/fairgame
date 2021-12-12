YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

if pyenv --version ; then
    printf "${GREEN}You have 'pyenv' installed!${NC} \n"
    else

    printf "\n${YELLOW}You do not have 'pyenv' installed.
    If you are not on Python 3.8, This installation will fail!${NC} \n"

fi


python -m pip install pipenv
python -m pipenv install

echo -e "\n${GREEN}------===== Installed! You can now use the launchers!=====------${NC} \n"

exit






