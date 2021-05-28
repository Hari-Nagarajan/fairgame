YELLOW='\033[1;33m'
RED='\033[0;32m'
NC='\033[0m'

if pyenv --version ; then

    else

    printf "\n${YELLOW}You do not have 'pyenv' installed.
    If you are not on Python 3.8, This installation will fail!${NC} \n"

fi


python -m pip install pipenv
python -m pipenv install

echo -e "\n${RED}------===== Installed! You can now use the launchers!=====------${NC} \n"

exit






